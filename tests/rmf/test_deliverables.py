"""Behavioral tests for ``securetrace.rmf.deliverables`` (backlog B4).

Pinned acceptance criteria (BACKLOG.md B4; spec ``algorithms/rmf-evidence-bundle.md`` §6):

- **C1 determinism** — two runs over the same tree produce byte-identical bundles;
- **C2 SAR invariant** — every control cited in the SAR maps to at least one
  evidence file (asserted here);
- **C3 offline** — zero network: the module's import surface is stdlib +
  ``securetrace.*`` only (AST-asserted here);
- **C4 repo-agnostic** — missing evidence is a defined outcome
  (unsatisfied control), never a crash.

Sample data is the hand-built synthetic tree ``tests/fixtures/rmf/mini-repo/``
(no git, no network); the goldens in ``tests/fixtures/rmf/golden/`` pin the
exact rendering and manifest format (regenerate only with a documented
format change).
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from securetrace.errors import FormatError
from securetrace.rmf import deliverables

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "rmf" / "mini-repo"
GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "rmf" / "golden"

BUNDLE_FILES = ("SSP.md", "SAP.md", "SAR.md", "POAM.md", "manifest.json")


def _copy_repo(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    shutil.copytree(FIXTURE, dst)
    return dst


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _line_count(data: bytes) -> int:
    return data.count(b"\n") + (0 if not data or data.endswith(b"\n") else 1)


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.rmf

    assert securetrace.rmf.__doc__
    assert "RMF" in securetrace.rmf.__doc__


def test_deliverables_module_imports() -> None:
    assert deliverables.CATALOG
    assert callable(deliverables.collect_evidence)
    assert callable(deliverables.package)
    for name in ("render_ssp", "render_sap", "render_sar", "render_poam"):
        assert callable(getattr(deliverables, name))


def test_happy_path_bundle(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    evidence = deliverables.collect_evidence(repo)
    bundle = deliverables.package(evidence, repo, tmp_path / "bundle")
    assert bundle == tmp_path / "bundle"
    for name in BUNDLE_FILES:
        assert (bundle / name).is_file(), name
    # every corpus file is copied byte-identical under evidence/
    for entry in evidence.corpus:
        assert (bundle / "evidence" / entry.path).read_bytes() == (repo / entry.path).read_bytes()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "securetrace.rmf-bundle/1"
    assert manifest["git_head"] == "no-git"
    assert len(manifest["corpus"]) == 21  # 20 fixed paths + 1 algorithm doc
    assert len(manifest["controls"]) == 11
    assert all(control["satisfied"] for control in manifest["controls"])
    # I5: manifest hashes bind the exact bytes written
    for name in ("SSP", "SAP", "SAR", "POAM"):
        assert manifest["docs"][name] == _sha256((bundle / f"{name}.md").read_bytes())
    for row in manifest["corpus"]:
        assert row["sha256"] == _sha256((repo / row["path"]).read_bytes())


def test_happy_path_state(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    evidence = deliverables.collect_evidence(repo)
    assert evidence.git_head == "no-git"
    assert evidence.backlog is not None
    assert evidence.backlog.total == 2
    assert dict(evidence.backlog.by_status) == {"DONE": 1, "OPEN": 1}
    assert evidence.backlog.open_items == (("B2", "Second item", "OPEN"),)
    assert evidence.lessons is not None
    assert evidence.lessons.total == 1
    assert dict(evidence.lessons.by_severity) == {"high": 1}
    assert evidence.algorithms.total == 1
    assert evidence.algorithms.docs == ("algorithms/fixture.md",)


def test_determinism_two_runs_byte_identical(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bundle_a = deliverables.package(deliverables.collect_evidence(repo), repo, tmp_path / "a")
    bundle_b = deliverables.package(deliverables.collect_evidence(repo), repo, tmp_path / "b")
    assert _tree_bytes(bundle_a) == _tree_bytes(bundle_b)


def test_golden_renderings(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bundle = deliverables.package(deliverables.collect_evidence(repo), repo, tmp_path / "bundle")
    for name in BUNDLE_FILES:
        assert (bundle / name).read_bytes() == (GOLDEN / name).read_bytes(), name


def test_sar_invariant_catalog_and_rows(tmp_path: Path) -> None:
    # I2 at catalog level: every control cites at least one evidence path.
    for spec in deliverables.CATALOG:
        assert len(spec.evidence) >= 1, spec.control_id
    # ...and behaviorally on the evaluated snapshot.
    repo = _copy_repo(tmp_path)
    evidence = deliverables.collect_evidence(repo)
    corpus = {entry.path for entry in evidence.corpus}
    assert len(evidence.controls) == len(deliverables.CATALOG)
    for control in evidence.controls:
        assert len(control.evidence) >= 1
        for path in control.evidence:
            assert path in corpus, f"{control.spec.control_id}: {path} not in corpus"


def test_missing_evidence_flips_exactly_three(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    for rel in ("BACKLOG.md", "requirements.txt", "dist/sbom.json"):
        (repo / rel).unlink()
    evidence = deliverables.collect_evidence(repo)
    unsatisfied = {
        control.spec.control_id for control in evidence.controls if not control.satisfied
    }
    assert unsatisfied == {"ST-01", "SC-01", "SB-01"}
    bundle = deliverables.package(evidence, repo, tmp_path / "bundle")
    poam = (bundle / "POAM.md").read_text(encoding="utf-8")
    for cid in ("ST-01", "SC-01", "SB-01"):
        assert cid in poam
    sar = (bundle / "SAR.md").read_text(encoding="utf-8")
    assert "NOT SATISFIED" in sar
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"]["backlog"] is None
    assert [c["satisfied"] for c in manifest["controls"]].count(True) == 8


def test_empty_repo(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    evidence = deliverables.collect_evidence(empty)
    assert evidence.corpus == ()
    assert evidence.backlog is None
    assert evidence.lessons is None
    assert evidence.algorithms.total == 0
    assert all(not control.satisfied for control in evidence.controls)
    bundle = deliverables.package(evidence, empty, tmp_path / "bundle")
    for name in BUNDLE_FILES:
        assert (bundle / name).is_file(), name
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["corpus"] == []
    assert all(not control["satisfied"] for control in manifest["controls"])


def test_missing_repo_raises() -> None:
    with pytest.raises(FormatError):
        deliverables.collect_evidence(Path("/nonexistent/securetrace-fixture-repo"))


def test_import_surface_offline() -> None:
    source = Path(deliverables.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = set(sys.stdlib_module_names) | {"securetrace"}
    forbidden = {"urllib", "socket", "http", "requests", "httpx", "aiohttp", "ftplib", "smtplib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top not in forbidden, alias.name
                assert top in allowed, alias.name
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top not in forbidden, node.module
            assert top in allowed, node.module


def test_corpus_invariants(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    evidence = deliverables.collect_evidence(repo)
    paths = [entry.path for entry in evidence.corpus]
    assert paths == sorted(set(paths)), "corpus paths must be unique and strictly ascending"
    for entry in evidence.corpus:
        data = (repo / entry.path).read_bytes()
        assert entry.sha256 == _sha256(data)
        assert entry.lines == _line_count(data)
