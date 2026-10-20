---
name: securetrace
display-name: SecureTrace
description: Use when working in a SecureTrace-managed repo: backlog, lessons, algorithm-doc, and RMF-bundle tooling, gates, and document contracts.
---

# SecureTrace — agent usage guide

SecureTrace is the agentic toolset for secure, traceable, agent-performed
programming: deterministic backlogs, lessons records, algorithm-document
registries, CI/CD gate state, and DoW/DoD software RMF evidence bundles
(SSP / SAP / SAR / POA&M, Assess Only / cATO model).

This skill tells an agent **how to use the tools** in a SecureTrace-managed
repository (SecureTrace itself, or a downstream project that adopts the
toolset). Read it before running SecureTrace commands.

## Repository map (what lives where)

| Path | What it is | Managed by |
|---|---|---|
| `BACKLOG.md` | Work queue + evidence, machine-indexed | `securetrace backlog` / `scripts/backlog_index.py` |
| `LESSONS_LEARNED.md` | Lessons log + machine index | `securetrace lessons` / `scripts/manage_lessons.py` |
| `algorithms/INDEX.md` | Algorithm-document registry (one row per doc) | `@algorithm-records-keeper` conventions |
| `algorithms/<slug>.md` | Algorithm documents (design records, doc-before-code) | `securetrace algorithms` / `scripts/algorithm_index.py` |
| `src/securetrace/` | The tool package (pure core + CLI) | tests (1:1 mirror in `tests/`) |
| `scripts/` | Thin CLI wrappers for hooks/Makefile/CI | vendored, surface pinned by tests |
| `hooks/` | git hooks (pre-commit, commit-msg, pre-push) | `core.hooksPath` |
| `Makefile` | The single gate entrypoint | mirrored by `hooks/` + `.github/workflows/` |
| `docs/dow-requirements.md` | DoW/DoD RMF + Software Acquisition Pathway requirements (the "why") | research record |
| `artifacts/rmf/<date>/` | Built RMF evidence bundles | `securetrace rmf build` / `make rmf-bundle` |

## The `securetrace` CLI

Console entrypoint: `securetrace` (or `.venv/bin/python -m securetrace`).
**Exit codes: 0 = ok, 1 = stale index, 2 = malformed file or rejected input.**

### backlog — BACKLOG.md line index

- `securetrace backlog sync <BACKLOG.md>` — rewrite the index in place
  (idempotent). **Run after every BACKLOG.md edit.**
- `securetrace backlog check <BACKLOG.md>` — verify the index is current;
  exit 1 if stale. This is the CI gate form (in `make docs-check`).

### lessons — LESSONS_LEARNED.md record

- `securetrace lessons init <file>` — create a new record.
- `securetrace lessons add <file> --title T --context C --pitfall P
  --solution S [--category …] [--severity …] [--recorded YYYY-MM-DD]
  [--supersedes LLT-NNNN] [--prevention …] [--references …]` — append a
  lesson and update the index. **Never hand-edit the index block or the
  `<!-- LLT:ENTRY:… -->` markers.**
- `securetrace lessons sync <file>` — regenerate the index from the entries.
- `securetrace lessons check <file>` — validate structure, fields, and index
  freshness (the CI gate form).
- `securetrace lessons next-id <file>` — print the next `LLT-NNNN` id.

Category vocabulary: debugging, architecture, testing, performance, security,
dependencies, tooling, environment, process, data, other. Severity: low,
medium, high, critical.

### algorithms — algorithm-document indexes

- `securetrace algorithms sync <doc.md>` — rewrite the doc's line index.
- `securetrace algorithms check <doc.md>` — exit 1 if stale. `make docs-check`
  runs `check` over every `algorithms/*.md` except `INDEX.md`.

### rmf — RMF evidence bundles

- `securetrace rmf build <repo-root> [--outdir DIR]` — build the dated
  SSP/SAP/SAR/POA&M bundle + canonical manifest from repository state
  (deterministic, zero network; default outdir `artifacts/rmf/<today>`).
  `make rmf-bundle` wraps it.

## scripts/ wrappers (what hooks, Makefile, and CI actually call)

Hooks/Makefile/CI invoke the vendored wrappers — never machine-local skill
paths (LLT-0002). They expose the same surface as the CLI:

- `scripts/backlog_index.py <BACKLOG.md> [--check]`
- `scripts/manage_lessons.py {init,add,sync,check,next-id} …`
- `scripts/algorithm_index.py <doc.md> [--check]`
- `scripts/check_workflow_yaml.py [FILE…]` — strict-parse workflow YAML and
  hard-fail on duplicate mapping keys (default: `.github/workflows/*.yml`
  and `*.yaml`)
- `scripts/changed_tests.py` — map changed modules to their tests
  (pre-commit stage 6/6, fast)

## Gates (one definition, three enforcement points)

Gate definitions live in the **Makefile**; `hooks/` and
`.github/workflows/` are thin wrappers. **Adding a gate means adding it to
the Makefile, the matching hook, and CI in the same change.** No bypass:
a gate failure blocks commit/push/CI.

| Gate | Where | Stages |
|---|---|---|
| `make gate` | local + CI quality | format-check → lint → docs-check → workflow-check → build → test |
| `pre-commit` | hook (6 stages) | format-check → lint → docs-check → workflow-check → gitleaks (staged) → changed-module tests |
| `commit-msg` | hook | Conventional Commits |
| `pre-push` | hook (3 stages) | compileall → full test suite → gitleaks (full history) |
| CI `quality` | Actions | `make setup-ci` + format-check, lint, docs-check, workflow-check, build, test |
| CI `security` | Actions | gitleaks (full history) + pip-audit + CycloneDX SBOM |
| Release | Actions (tag `v*`) | gate → sdist + wheel → cosign keyless signing + SLSA provenance → immutable GitHub release with release attestation |

Useful targets: `make setup` (fresh clone: venv + pinned deps + hooks),
`make lock` (regenerate pinned hashed lockfiles), `make sbom`,
`make dependency-audit`, `make rmf-bundle`, `make help` (everything).

## Document contracts (the parts that must stay true)

1. **BACKLOG.md** — one `<!-- BACKLOG:ITEM:B<n> -->` marker per item; heading
   `## B<n>. Title — **STATUS**` with STATUS ∈ OPEN / IN PROGRESS / DONE /
   CANCELLED; a `**Priority:**` field (High/Medium/Low); index TSV between
   `<!-- INDEX:BEGIN/END -->` regenerated after **every** edit
   (`sync` then `check`); closeouts carry commit shas + CI + verification
   numbers + version (or `none`).
2. **LESSONS_LEARNED.md** — entries with bold field lines between
   `<!-- LLT:ENTRY:… -->` markers; index TSV between `LLT:INDEX:BEGIN/END`;
   never hand-edit markers or index — `add`/`sync`/`check` only.
3. **algorithms/** — one registry row per doc in `algorithms/INDEX.md`; the
   row `Version` must equal the doc's `METADATA` version; doc before code,
   and doc + code land atomically; rows are never deleted (mark
   `deprecated`).
4. **.github/workflows** — pure ASCII, no duplicate mapping keys; both files
   pass `scripts/check_workflow_yaml.py` in every gate.
5. **Dependencies** — pinned + hashed (`requirements*.txt` via pip-compile);
   CI installs with `--require-hashes`; any new dependency needs a one-line
   justification in the `.in` manifest.
6. **Actions** — SHA-pinned, with the version noted in a comment.

## The agent's working loop

1. Backlog entry first (work item 1), with acceptance criteria.
2. Doc cycle if an algorithm/design is involved (`algorithms/`).
3. Tests RED → 4. implementation GREEN → 5. `make gate` green.
6. Conventional Commit (pre-commit gate) → 7. `git push` (pre-push gate).
8. CI green (quality + security + SonarCloud) — verify check-runs on the
   pushed sha.
9. Closeout in the backlog with evidence, index regenerated, then the next
   item.

Record lessons **as they are learned** (dedupe against
`LESSONS_LEARNED.md` first), not in a batch at the end.

## RMF bundles (the DoW deliverables)

`make rmf-bundle` (or `securetrace rmf build .`) produces a dated,
deterministic evidence bundle — SSP / SAP / SAR / POA&M + manifest —
assembled from repository state (gate state, backlog, lessons, algorithm
registry, lockfiles). Reruns are byte-identical; zero network. Regenerate
per release (tag `v*` pipeline) for the cATO / speed-of-relevance model.
Requirements + sources: `docs/dow-requirements.md` (RMF per DoDI 8510.01 /
NIST SP 800-37; Software Acquisition Pathway per DoDI 5000.87).

## Pitfalls (from LESSONS_LEARNED.md — read the file for full entries)

- zsh does not word-split unquoted variables (LLT-0003) — quote all
  expansions and URLs.
- Duplicate YAML mapping keys: local parsers tolerate them, GitHub
  hard-fails (LLT-0017/0018) — run `make workflow-check` after any workflow
  edit.
- Hooks/CI must call `scripts/` wrappers, never `~/.lmstudio/skills/…`
  (LLT-0002).
- `pip --require-hashes` breaks on clean runners if any transitive dep is
  unpinned (LLT-0005) — use `make lock`.
- A gitleaks config with `WITHOUT` rules is a zero-rule no-op scanner
  (LLT-0004).
- GitHub JSON API responses can contain control characters — parse with
  `json.load(f, strict=False)` (LLT-0016).
- SonarCloud gate verdicts are per-analysis: fixes do not re-evaluate an
  already-analyzed commit (LLT-0031); S8786 is shape-sensitive, not just
  complexity-sensitive (LLT-0033) — verify via the live issues API.

## Keeping this skill current

This file is the canonical agent-facing usage guide. When any command,
gate, script, or document contract above changes, update `SKILL.md` **in
the same change** — `tests/test_skill_doc.py` asserts the front matter is
valid and every core command in this list is still referenced. Do not fork
this content into other documents; link here instead.
