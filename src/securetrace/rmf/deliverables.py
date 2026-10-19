"""Deterministic RMF deliverable builder (backlog B4).

Spec: ``algorithms/rmf-evidence-bundle.md``. Three layers, in order:

1. :func:`collect_evidence` — a pure snapshot of the worktree: the evidence
   corpus (fixed paths + ``algorithms/*.md``), the process state (backlog,
   lessons, algorithm records), and the evaluated control catalog;
2. :func:`render_ssp` / :func:`render_sap` / :func:`render_sar` /
   :func:`render_poam` — pure string functions of the snapshot (no I/O, no
   clock — invariant I3);
3. :func:`package` — the only I/O beyond reading: writes the corpus copies,
   the four documents, and the canonical ``manifest.json``.

Stdlib-only core (acceptance C3): the only subprocess is a local, offline
``git rev-parse HEAD`` (degrades to ``"no-git"`` on any failure). There are
no wall-clock reads anywhere in this module — the date lives only in the
caller-supplied bundle directory name (CLI/Makefile), which is what makes
byte-identical reruns (acceptance C1) hold.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from securetrace import __version__
from securetrace.algorithms import registry
from securetrace.backlog import index as backlog_index
from securetrace.errors import FormatError
from securetrace.lessons import record

__all__ = [
    "BacklogState",
    "CATALOG",
    "ControlResult",
    "ControlSpec",
    "Evidence",
    "EvidenceFile",
    "FIXED",
    "AlgorithmsState",
    "LessonsState",
    "collect_evidence",
    "package",
    "render_poam",
    "render_sap",
    "render_sar",
    "render_ssp",
]

SCHEMA = "securetrace.rmf-bundle/1"
CATALOG_VERSION = 1
OPEN_STATUSES = ("OPEN", "IN_PROGRESS")
GIT_TIMEOUT_SECONDS = 10

_B_ITEM_RE = re.compile(r"^B(?a:\d)+$")


@dataclass(frozen=True)
class EvidenceFile:
    """One corpus entry: repo-relative POSIX path, exact bytes bound by SHA-256."""

    path: str
    sha256: str
    lines: int


@dataclass(frozen=True)
class ControlSpec:
    """One row of the fixed control catalog (I2: ``evidence`` is never empty)."""

    control_id: str
    title: str
    evidence: tuple[str, ...]
    method: str
    remediation: str


@dataclass(frozen=True)
class ControlResult:
    """An evaluated catalog row; ``evidence`` includes ST-03's discovered docs."""

    spec: ControlSpec
    evidence: tuple[str, ...]
    present: tuple[str, ...]
    satisfied: bool


@dataclass(frozen=True)
class BacklogState:
    """Parsed BACKLOG.md item summary (``None`` when the anchor file is absent)."""

    total: int
    by_status: tuple[tuple[str, int], ...]
    open_items: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class LessonsState:
    """Parsed LESSONS_LEARNED.md summary (``None`` when absent or broken)."""

    total: int
    by_severity: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AlgorithmsState:
    """Algorithm / design record summary (always present; ``total`` may be 0)."""

    total: int
    docs: tuple[str, ...]


@dataclass(frozen=True)
class Evidence:
    """The snapshot the renderers and the manifest consume (pure, frozen)."""

    corpus: tuple[EvidenceFile, ...]
    backlog: BacklogState | None
    lessons: LessonsState | None
    algorithms: AlgorithmsState
    controls: tuple[ControlResult, ...]
    git_head: str
    catalog_version: int


#: Fixed control catalog — defined, not discovered (catalog order is the render order).
CATALOG: tuple[ControlSpec, ...] = (
    ControlSpec(
        "ST-01",
        "Deterministic work records (backlog)",
        ("BACKLOG.md",),
        "backlog index check",
        "Restore BACKLOG.md and regenerate its index (securetrace backlog sync).",
    ),
    ControlSpec(
        "ST-02",
        "Quality-control / lessons history",
        ("LESSONS_LEARNED.md",),
        "lessons record check",
        "Restore LESSONS_LEARNED.md and regenerate its index (securetrace lessons sync).",
    ),
    ControlSpec(
        "ST-03",
        "Algorithm / design records",
        ("algorithms/INDEX.md",),
        "per-doc index check",
        "Restore algorithms/INDEX.md and each algorithm document's index "
        "(securetrace algorithms sync).",
    ),
    ControlSpec(
        "ST-04",
        "Architecture & requirements traceability",
        ("ARCHITECTURE.md", "docs/dow-requirements.md"),
        "presence",
        "Restore ARCHITECTURE.md and docs/dow-requirements.md.",
    ),
    ControlSpec(
        "SC-01",
        "Pinned, hashed dependency manifests",
        ("requirements.in", "requirements-dev.in", "requirements.txt", "requirements-dev.txt"),
        "presence",
        "Regenerate the pinned lockfiles (make lock).",
    ),
    ControlSpec(
        "SC-02",
        "Secret-scanning policy & hooks",
        (".gitleaks.toml", "hooks/pre-commit", "hooks/pre-push"),
        "presence",
        "Restore the gitleaks config and the pre-commit / pre-push hooks.",
    ),
    ControlSpec(
        "CI-01",
        "Gate definitions (local + CI)",
        ("Makefile", ".github/workflows/ci.yml"),
        "presence",
        "Restore the Makefile gate and the CI workflow.",
    ),
    ControlSpec(
        "QA-01",
        "Code quality configuration",
        ("pyproject.toml", "sonar-project.properties"),
        "presence",
        "Restore pyproject.toml and sonar-project.properties.",
    ),
    ControlSpec(
        "REL-01",
        "License & packaging metadata",
        ("LICENSE", "pyproject.toml"),
        "presence",
        "Restore LICENSE and the packaging metadata in pyproject.toml.",
    ),
    ControlSpec(
        "REL-02",
        "Release pipeline with provenance",
        (".github/workflows/release.yml",),
        "presence",
        "Restore .github/workflows/release.yml.",
    ),
    ControlSpec(
        "SB-01",
        "Software bill of materials",
        ("dist/sbom.json",),
        "presence",
        "Generate the SBOM (make sbom).",
    ),
)

#: The fixed evidence corpus: the 19 unique paths the catalog cites, plus README.md.
FIXED: tuple[str, ...] = (
    "BACKLOG.md",
    "LESSONS_LEARNED.md",
    "algorithms/INDEX.md",
    "ARCHITECTURE.md",
    "docs/dow-requirements.md",
    "requirements.in",
    "requirements-dev.in",
    "requirements.txt",
    "requirements-dev.txt",
    ".gitleaks.toml",
    "hooks/pre-commit",
    "hooks/pre-push",
    "Makefile",
    ".github/workflows/ci.yml",
    "pyproject.toml",
    "sonar-project.properties",
    "LICENSE",
    ".github/workflows/release.yml",
    "dist/sbom.json",
    "README.md",
)


def _line_count(data: bytes) -> int:
    """Physical lines: ``b"\\n"`` count plus a trailing partial line."""
    return data.count(b"\n") + (0 if not data or data.endswith(b"\n") else 1)


def _algo_doc_paths(root: Path) -> tuple[str, ...]:
    """Sorted repo-relative paths of the algorithm documents (``algorithms/*.md``
    minus the registry ``INDEX.md``, which carries no section index by design)."""
    if not (root / "algorithms").is_dir():
        return ()
    docs = [
        p.relative_to(root).as_posix()
        for p in root.glob("algorithms/*.md")
        if p.is_file() and p.name != "INDEX.md"
    ]
    return tuple(sorted(docs))


def _backlog_state(text: str | None) -> BacklogState | None:
    """Summarize the backlog items; malformed → ``None`` (defined outcome, C4)."""
    if text is None:
        return None
    try:
        rows = backlog_index.index_rows(text)
    except FormatError:
        return None
    items = [row for row in rows if _B_ITEM_RE.match(row.id)]
    by_status: dict[str, int] = {}
    for row in items:
        by_status[row.status] = by_status.get(row.status, 0) + 1
    open_items = tuple(
        (row.id, row.title, row.status)
        for row in sorted(
            (row for row in items if row.status in OPEN_STATUSES), key=lambda r: int(r.id[1:])
        )
    )
    return BacklogState(
        total=len(items), by_status=tuple(sorted(by_status.items())), open_items=open_items
    )


def _lessons_state(text: str | None) -> LessonsState | None:
    """Summarize the lessons record; broken or stale → ``None`` (C4)."""
    if text is None:
        return None
    try:
        if record.structural_errors(text) or not record.index_is_fresh(text):
            return None
    except FormatError:
        return None
    entries, _ = record.parse_entries(text.split("\n"))
    by_severity: dict[str, int] = {}
    for entry in entries:
        severity = entry.fields.get("Severity", "")
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return LessonsState(total=len(entries), by_severity=tuple(sorted(by_severity.items())))


def _control_ok(spec: ControlSpec, texts: dict[str, str], algo_docs: tuple[str, ...]) -> bool:
    """Live checker for a control (vacuous for ``presence`` methods)."""
    if spec.control_id == "ST-01":
        text = texts.get("BACKLOG.md")
        return text is not None and backlog_index.is_fresh(text)
    if spec.control_id == "ST-02":
        text = texts.get("LESSONS_LEARNED.md")
        if text is None:
            return False
        try:
            return record.structural_errors(text) == [] and record.index_is_fresh(text)
        except FormatError:
            return False
    if spec.control_id == "ST-03":
        # INDEX.md is the registry (no section index by design); the docs are checked.
        for doc in algo_docs:
            text = texts.get(doc)
            if text is None or not registry.is_fresh(text):
                return False
        return True
    return True


def _git_head(root: Path) -> str:
    """Local, offline ``git rev-parse HEAD``; any failure degrades to ``"no-git"``."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "no-git"
    if proc.returncode != 0:
        return "no-git"
    head = proc.stdout.strip()
    return head or "no-git"


def collect_evidence(repo: str | Path) -> Evidence:
    """Snapshot the worktree: corpus, process state, and the evaluated catalog.

    Reads only the fixed corpus (C3/C4); never walks the tree.

    Raises:
        FormatError: ``repo`` is missing or not a directory.
    """
    root = Path(repo)
    if not root.is_dir():
        raise FormatError(f"{repo}: repository root is missing or not a directory")
    algo_docs = _algo_doc_paths(root)
    corpus: list[EvidenceFile] = []
    texts: dict[str, str] = {}
    for rel in sorted(set(FIXED) | set(algo_docs)):
        file = root / rel
        if not file.is_file():
            continue
        data = file.read_bytes()
        corpus.append(EvidenceFile(rel, hashlib.sha256(data).hexdigest(), _line_count(data)))
        with contextlib.suppress(UnicodeDecodeError):
            texts[rel] = data.decode("utf-8")  # checkers needing text treat absent as not-ok
    corpus_paths = {entry.path for entry in corpus}
    controls: list[ControlResult] = []
    for spec in CATALOG:
        resolved = spec.evidence if spec.control_id != "ST-03" else spec.evidence + algo_docs
        present = tuple(p for p in resolved if p in corpus_paths)
        satisfied = len(present) == len(resolved) and _control_ok(spec, texts, algo_docs)
        controls.append(ControlResult(spec, resolved, present, satisfied))
    return Evidence(
        corpus=tuple(corpus),
        backlog=_backlog_state(texts.get("BACKLOG.md")),
        lessons=_lessons_state(texts.get("LESSONS_LEARNED.md")),
        algorithms=AlgorithmsState(total=len(algo_docs), docs=algo_docs),
        controls=tuple(controls),
        git_head=_git_head(root),
        catalog_version=CATALOG_VERSION,
    )


def _evidence_cell(paths: tuple[str, ...]) -> str:
    return ", ".join(f"`{p}`" for p in paths)


def _fmt_counts(pairs: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{name} {count}" for name, count in pairs) if pairs else "none"


def _finding(control: ControlResult) -> str:
    present = set(control.present)
    missing = [p for p in control.evidence if p not in present]
    parts = []
    if missing:
        parts.append("missing evidence: " + ", ".join(f"`{p}`" for p in missing))
    if not control.satisfied and not missing:
        parts.append(f"live checker failed ({control.spec.method})")
    return "; ".join(parts)


def _satisfied_count(evidence: Evidence) -> int:
    return sum(1 for control in evidence.controls if control.satisfied)


def _baseline_table(evidence: Evidence) -> list[str]:
    lines = ["| Control | Title | Method | Evidence |", "|---|---|---|---|"]
    for control in evidence.controls:
        lines.append(
            f"| {control.spec.control_id} | {control.spec.title} | {control.spec.method} "
            f"| {_evidence_cell(control.evidence)} |"
        )
    return lines


def _records_lines(evidence: Evidence) -> list[str]:
    backlog = evidence.backlog
    if backlog is None:
        lines = ["- Backlog: absent (ST-01 not satisfied)"]
    else:
        open_items = ", ".join(item[0] for item in backlog.open_items) or "none"
        lines = [
            f"- Backlog: {backlog.total} item(s); {_fmt_counts(backlog.by_status)}; "
            f"open: {open_items}"
        ]
    lessons = evidence.lessons
    if lessons is None:
        lines.append("- Lessons learned: absent (ST-02 not satisfied)")
    else:
        lines.append(
            f"- Lessons learned: {lessons.total} entry(ies); {_fmt_counts(lessons.by_severity)}"
        )
    docs = evidence.algorithms
    suffix = "" if not docs.docs else " — " + ", ".join(f"`{d}`" for d in docs.docs)
    lines.append(f"- Algorithm / design records: {docs.total} document(s){suffix}")
    return lines


def _related_docs() -> list[str]:
    return [
        "- `docs/dow-requirements.md` — DoD software RMF / Software Acquisition Pathway reference",
        "- `ARCHITECTURE.md` — module map",
        "- `LESSONS_LEARNED.md` — quality-control history",
        "- `algorithms/` — algorithm / design records",
    ]


def render_ssp(evidence: Evidence) -> str:
    """Render the System Security Plan (pure function of ``evidence``)."""
    lines: list[str] = []
    lines.append("# System Security Plan (SSP)")
    lines.append("")
    lines.append('SecureTrace "Assess Only" RMF deliverable — SSP scaffold. Generated offline')
    lines.append("from repository state by `securetrace rmf build`; `manifest.json` binds this")
    lines.append("document to the exact evidence bytes.")
    lines.append("")
    lines.append("## 1. System overview")
    lines.append("")
    lines.append("SecureTrace is agentic tooling for secure, traceable software development:")
    lines.append("deterministic backlogs, lessons learned, algorithm records, CI/CD gates, and")
    lines.append("DoW RMF package deliverables (see `docs/dow-requirements.md`).")
    lines.append("")
    lines.append(
        f"Assessed at git HEAD `{evidence.git_head}`; control catalog v{evidence.catalog_version}; "
        f"evidence corpus: {len(evidence.corpus)} file(s)."
    )
    lines.append("")
    lines.append("## 2. Work and quality records")
    lines.append("")
    lines.extend(_records_lines(evidence))
    lines.append("")
    lines.append("## 3. Control baseline")
    lines.append("")
    lines.extend(_baseline_table(evidence))
    lines.append("")
    lines.append("## 4. Supply chain")
    lines.append("")
    by_id = {control.spec.control_id: control for control in evidence.controls}
    for cid in ("SC-01", "SC-02", "SB-01"):
        control = by_id[cid]
        state = "satisfied" if control.satisfied else "not satisfied"
        lines.append(f"- {control.spec.title}: {state} ({_evidence_cell(control.evidence)})")
    lines.append("")
    lines.append("## 5. Related documents")
    lines.append("")
    lines.extend(_related_docs())
    return "\n".join(lines) + "\n"


def render_sap(evidence: Evidence) -> str:
    """Render the System and Security Assessment Plan (pure function of ``evidence``)."""
    lines: list[str] = []
    lines.append("# System and Security Assessment Plan (SAP)")
    lines.append("")
    lines.append("Defines how the control baseline in `SSP.md` §3 is assessed: fully local and")
    lines.append("offline, from the evidence corpus below (no network access, no wall clock).")
    lines.append("")
    lines.append("## 1. Purpose and scope")
    lines.append("")
    lines.append(
        f"Assess the repository at git HEAD `{evidence.git_head}` against the "
        f"{len(evidence.controls)}-control baseline using only the corpus files listed in §4."
    )
    lines.append("")
    lines.append("## 2. Control selection")
    lines.append("")
    lines.append("| Control | Title | Method |")
    lines.append("|---|---|---|")
    for control in evidence.controls:
        lines.append(
            f"| {control.spec.control_id} | {control.spec.title} | {control.spec.method} |"
        )
    lines.append("")
    lines.append("## 3. Assessment method")
    lines.append("")
    lines.append("- Collect: hash (SHA-256) and line-count every corpus file; parse the process")
    lines.append("  state (backlog, lessons, algorithm records) with the SecureTrace B3 cores.")
    lines.append("- Evaluate: a control is SATISFIED iff every evidence file it cites is present")
    lines.append("  and any live checker (backlog index, lessons record, per-doc index) passes.")
    lines.append("- Render: the SSP/SAP/SAR/POA&M are pure renderings of the snapshot;")
    lines.append("  `manifest.json` binds every corpus file and document to its SHA-256.")
    lines.append("")
    lines.append("## 4. Evidence corpus")
    lines.append("")
    lines.append("| Path | Lines | SHA-256 |")
    lines.append("|---|---|---|")
    for entry in evidence.corpus:
        lines.append(f"| `{entry.path}` | {entry.lines} | {entry.sha256} |")
    return "\n".join(lines) + "\n"


def render_sar(evidence: Evidence) -> str:
    """Render the Security Assessment Report (pure function of ``evidence``)."""
    satisfied = _satisfied_count(evidence)
    total = len(evidence.controls)
    lines: list[str] = []
    lines.append("# Security Assessment Report (SAR)")
    lines.append("")
    lines.append("## 1. Summary")
    lines.append("")
    lines.append(f"- Controls assessed: {total}")
    lines.append(f"- Satisfied: {satisfied}")
    lines.append(f"- Not satisfied: {total - satisfied}")
    lines.append(f"- Git HEAD: `{evidence.git_head}`")
    lines.append("")
    lines.append("## 2. Control results")
    lines.append("")
    lines.append("| Control | Title | Evidence | Result |")
    lines.append("|---|---|---|---|")
    for control in evidence.controls:
        result = "SATISFIED" if control.satisfied else "NOT SATISFIED"
        lines.append(
            f"| {control.spec.control_id} | {control.spec.title} "
            f"| {_evidence_cell(control.evidence)} | {result} |"
        )
    lines.append("")
    lines.append("## 3. SAR invariant")
    lines.append("")
    lines.append("Every control cited above maps to at least one evidence file (spec invariant I2;")
    lines.append("asserted by the test suite). Evidence files are byte-identical copies under")
    lines.append("`evidence/`; `manifest.json` records their SHA-256.")
    lines.append("")
    lines.append("## 4. Findings")
    lines.append("")
    lines.append("See `POAM.md` for the plan of action and milestones.")
    return "\n".join(lines) + "\n"


def render_poam(evidence: Evidence) -> str:
    """Render the Plan of Action and Milestones (pure function of ``evidence``)."""
    lines: list[str] = []
    lines.append("# Plan of Action and Milestones (POA&M)")
    lines.append("")
    lines.append("## 1. Findings")
    lines.append("")
    findings = [control for control in evidence.controls if not control.satisfied]
    if not findings:
        lines.append("None — all controls satisfied.")
    else:
        lines.append("| # | Control | Finding | Remediation |")
        lines.append("|---|---|---|---|")
        for number, control in enumerate(findings, start=1):
            lines.append(
                f"| {number} | {control.spec.control_id} | {_finding(control)} | "
                f"{control.spec.remediation} |"
            )
    lines.append("")
    lines.append("## 2. Milestones (open backlog items)")
    lines.append("")
    backlog = evidence.backlog
    if backlog is None or not backlog.open_items:
        lines.append("none")
    else:
        lines.append("| Item | Title | Status |")
        lines.append("|---|---|---|")
        for item_id, title, status in backlog.open_items:
            lines.append(f"| {item_id} | {title} | {status} |")
    return "\n".join(lines) + "\n"


def _backlog_json(state: BacklogState | None) -> dict[str, object] | None:
    if state is None:
        return None
    return {
        "total": state.total,
        "by_status": dict(state.by_status),
        "open_items": [list(item) for item in state.open_items],
    }


def _lessons_json(state: LessonsState | None) -> dict[str, object] | None:
    if state is None:
        return None
    return {"total": state.total, "by_severity": dict(state.by_severity)}


def _manifest(evidence: Evidence, docs: dict[str, str]) -> str:
    """Canonical manifest: sorted keys, indent 2, exactly one trailing LF."""
    payload = {
        "schema": SCHEMA,
        "catalog_version": evidence.catalog_version,
        "generated_by": f"securetrace {__version__}",
        "git_head": evidence.git_head,
        "corpus": [
            {"path": entry.path, "sha256": entry.sha256, "lines": entry.lines}
            for entry in evidence.corpus
        ],
        "docs": {
            name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in docs.items()
        },
        "controls": [
            {
                "control_id": control.spec.control_id,
                "title": control.spec.title,
                "method": control.spec.method,
                "evidence": list(control.evidence),
                "present": list(control.present),
                "satisfied": control.satisfied,
            }
            for control in evidence.controls
        ],
        "state": {
            "backlog": _backlog_json(evidence.backlog),
            "lessons": _lessons_json(evidence.lessons),
            "algorithms": {
                "total": evidence.algorithms.total,
                "docs": list(evidence.algorithms.docs),
            },
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def package(evidence: Evidence, repo: str | Path, outdir: str | Path) -> Path:
    """Write the bundle: corpus copies, four documents, canonical manifest.

    This is the only layer with write I/O; the bytes it writes are a pure
    function of ``evidence`` (and the corpus bytes read from ``repo``), so
    two runs over the same tree are byte-identical (C1).
    """
    root = Path(repo)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    ev_dir = out / "evidence"
    ev_dir.mkdir(exist_ok=True)
    for entry in evidence.corpus:
        dest = ev_dir / entry.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((root / entry.path).read_bytes())
    docs = {
        "SSP": render_ssp(evidence),
        "SAP": render_sap(evidence),
        "SAR": render_sar(evidence),
        "POAM": render_poam(evidence),
    }
    for name, text in docs.items():
        (out / f"{name}.md").write_text(text, encoding="utf-8")
    (out / "manifest.json").write_text(_manifest(evidence, docs), encoding="utf-8")
    return out
