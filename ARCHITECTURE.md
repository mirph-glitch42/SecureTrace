# SecureTrace Architecture

> Structure document (pragmatic-programmer guard: keep this in sync with the
> code). Module map, gate architecture, and the mapping from DoW/DoD RMF
> requirements to this repository's artifacts.

## 1. Module map

```
src/securetrace/
├── __init__.py            # __version__, package docstring
├── __main__.py            # console entry: `securetrace …` argparse dispatch into cli
├── cli.py                 # B3 — subcommands, I/O, messages, exit codes (0/1/2)
├── errors.py              # B3 — typed errors (FormatError et al.) shared by subpackages
├── py.typed               # PEP 561 marker
├── backlog/               # B3 — deterministic backlog parsing/indexing (pure core)
│   ├── __init__.py
│   └── index.py           # marker scan, delta, idempotent TSV rewrite (format: frozen)
├── lessons/               # B3 — lessons-learned record management (pure core)
│   ├── __init__.py
│   └── record.py          # entry lifecycle (add/supersede/sync/check)
├── algorithms/            # B3 — algorithm document registry management (pure core)
│   ├── __init__.py
│   └── registry.py        # INDEX.md row ↔ document consistency
├── rmf/                   # B4 — RMF deliverable (package) generation
│   ├── __init__.py
│   └── deliverables.py    # SSP/SAP/SAR/POA&M scaffolds + evidence bundles
└── pipeline/              # CI/CD gate orchestration helpers
    ├── __init__.py
    └── gates.py           # gate definitions shared by hooks/Makefile/CI consumers
```

Tests mirror 1:1: `tests/<subpkg>/test_<module>.py` for the pure core, `tests/test_cli.py`
for the CLI surface (messages + exit codes), and `tests/test_package.py` for the
package itself. `tests/scripts/test_skill_scripts.py` pins the frozen CLI surface of
the thin `scripts/` wrappers against the skill's reference behavior.

**Naming distinction (important):** `algorithms/` (repo root) holds
*algorithm documents* per the `@algorithm-records-keeper` skill;
`src/securetrace/algorithms/` holds the *code* that manages those documents.
They are related but different artifacts — never merge them.

## 2. Gate architecture

One definition of every gate, three enforcement points:

```
            ┌────────────┐  thin wrappers   ┌─────────────────────┐
 hooks/ ───▶│  Makefile  │◀─────────────────│ .github/workflows/  │
 (git)      └─────┬──────┘                  │ ci.yml / release.yml│
                  │                         └─────────────────────┘
                  ▼
   scripts/  (index checks, changed-test mapping)
   .venv     (pinned, hashed deps: ruff, pytest, pip-audit, cyclonedx-py, build)
```

| Gate stage | pre-commit | pre-push | CI quality | CI security |
|---|---|---|---|---|
| format-check (ruff) | ✔ | — | ✔ | — |
| lint (ruff) | ✔ | — | ✔ | — |
| docs-check (backlog/lessons/algorithms indexes) | ✔ | — | ✔ | — |
| gitleaks | staged | full history | — | full history (action) |
| tests | changed-modules | full suite | full suite | — |
| compileall | — | ✔ | ✔ | — |
| pip-audit | — | — | — | ✔ |
| SBOM (CycloneDX) | — | — | — | ✔ |

Invariants:

1. **No bypass** — hooks are committed (`hooks/`, wired via `core.hooksPath`);
   a gate failure blocks commit/push/CI, full stop.
2. **Frozen index formats** — the TSV index blocks in `BACKLOG.md`,
   `LESSONS_LEARNED.md`, `algorithms/*.md` are the contract between the
   `scripts/` wrappers, the `securetrace` package API (B3), and CI.
   Roundtrip tests in `tests/scripts/` plus the package tests pin the behavior.
3. **Vendored skill scripts** — `scripts/{backlog_index,manage_lessons,algorithm_index}.py`
   were vendored from `~/.lmstudio/skills/…` (provenance in docstrings) so that
   hooks and CI never depend on machine-local paths; B3 turned them into thin
   wrappers over `securetrace.cli`, preserving the exact CLI surface, messages,
   and exit codes. See LESSONS_LEARNED.md LLT-0002.
4. **Pinned, hashed dependencies** — `requirements*.in` → `pip-compile
   --generate-hashes` → `requirements*.txt`; CI installs with `--require-hashes`.
5. **Conventional Commits** enforced locally (commit-msg) — release workflow
   triggers on `v*` tags only.

## 3. DoW/DoD RMF mapping

Full requirements + sources: [`docs/dow-requirements.md`](docs/dow-requirements.md).

| Requirement (source) | Implemented by | Status |
|---|---|---|
| RMF 7 steps, NIST SP 800-37 (DoDI 8510.01) | `securetrace.rmf` deliverable scaffolds (B4) | planned |
| **Assess Only** evidence for software below system level (DoDI 8510.01) | dated, deterministic evidence bundles from CI state (B4) | planned |
| SSP / SAP / SAR / POA&M | `securetrace.rmf` renderers with control→evidence mapping asserted in tests (B4) | planned |
| SWP ≤ 6-month increments, cATO / speed-of-relevance (DoDI 5000.87 + integration guidance) | tag-triggered release pipeline regenerating evidence per release (B1/B4/B5) | B1 done, B4/B5 planned |
| DevSecOps discipline (SSDF SP 800-218) | this repo's own gates as reference implementation (B1) | done |
| Deterministic process records (SWP QC expectation) | BACKLOG.md, LESSONS_LEARNED.md, algorithms/ (B1) | done |
| Supply-chain evidence | pinned hashed lockfiles + per-run and per-release SBOM (B1) | done |

## 4. Data flow (target, B4)

```
CI state (gate results, pip-audit, SBOM) ─┐
BACKLOG.md (work + evidence)            ─┼─▶ securetrace rmf build ─▶ evidence bundle (dated)
algorithms/ (design records)            ─┤         │
LESSONS_LEARNED.md (QC history)         ─┘         ├─▶ SSP / SAP / SAR / POA&M
                                                    └─▶ artifacts/rmf/<date>/ (release)
```

## 5. Non-goals

- No network access in library code (stdlib-only runtime; RMF bundles build
  offline from local artifacts).
- No secrets, ever — see `.gitleaks.toml`, hooks, and CI security job.
- Not an ATO authority: SecureTrace assembles *evidence*; authorization is a
  human (AO/DA) decision.
