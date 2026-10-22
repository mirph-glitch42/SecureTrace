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

## ⚠️ The three pipeline documents are generated — manual editing is not permitted

`BACKLOG.md`, `LESSONS_LEARNED.md`, and `algorithms/INDEX.md` are **pure
renders** of canonical-JSON stores under `data/` (B10). Every rendered doc
carries a generated header stating that manual editing is not permitted and
naming the CLI path that changes it.

- **All creation and update goes through the `securetrace` CLI.** The store
  is the source of truth; the `.md` is a byte-deterministic render of it.
- A hand edit is *detected and diagnosed*: `securetrace … check` exits 1
  naming `DOC_MODIFIED_OUTSIDE_APP` (doc touched outside the app) or
  `STORE_DRIFT` (store moved after render), plus the exact remediation
  command; `make docs-check` blocks commit and CI.
- To change data, mutate the store via the CLI (`upsert` / `progress` /
  `add`) — each verb re-renders the doc and refreshes the manifest in one
  commit. To repair a drifted doc, run the verb's `render`.
- **CLI paths stay inside the working directory:** every store/doc/manifest
  path a command accepts is resolved against the workspace base before any
  I/O; a path that would escape (a `../` chain, or an absolute path outside
  the repo) is rejected with exit 2 (contract C6, rule CC-010).
- **Gates are on the store surface (B10 WI 10):** `make docs-check`
  (pre-commit stage 3 and CI quality) runs `securetrace docs check-all`
  plus the ALRK TSV-index checks; `make docs-render` re-renders all three
  store docs and syncs the ALRK indexes. The legacy `scripts/backlog_index.py`
  and `scripts/manage_lessons.py` wrappers no longer exist.

## Repository map (what lives where)

| Path | What it is | Managed by |
|---|---|---|
| `data/backlog.json` | **Store** — source of truth for the backlog (canonical JSON) | `securetrace backlog …` |
| `data/lessons.json` | **Store** — source of truth for the lessons record | `securetrace lessons …` |
| `data/registry.json` | **Store** — source of truth for the algorithm registry | `securetrace algorithms …` |
| `data/manifest.json` | per-doc `store_sha256` + `doc_sha256` + renderer version | refreshed by every committing verb |
| `BACKLOG.md` | rendered backlog (work queue + evidence) — **generated, do not hand-edit** | `securetrace backlog render` |
| `LESSONS_LEARNED.md` | rendered lessons record — **generated, do not hand-edit** | `securetrace lessons render` |
| `algorithms/INDEX.md` | rendered algorithm registry — **generated, do not hand-edit** | `securetrace algorithms render` |
| `algorithms/<slug>.md` | algorithm documents (design records, doc-before-code) | `@algorithm-records-keeper` conventions; registry rows via `securetrace algorithms upsert` |
| `CONSISTENCY.md` | consistency registry (rules CC-001+; code-consistency-monitor) | agent — updated on every enforcement and every exception |
| `src/securetrace/` | the tool package (pure core + command layer) | tests (1:1 mirror in `tests/`) |
| `scripts/` | vendored helpers for hooks/Makefile/CI (ALRK TSV indexes, workflow YAML, changed tests) | surface pinned by tests |
| `hooks/` | git hooks (pre-commit, commit-msg, pre-push) | `core.hooksPath` |
| `Makefile` | the single gate entrypoint | mirrored by `hooks/` + `.github/workflows/` |
| `docs/dow-requirements.md` | DoW/DoD RMF + Software Acquisition Pathway requirements (the "why") | research record |
| `artifacts/rmf/<date>/` | built RMF evidence bundles | `securetrace rmf build` / `make rmf-bundle` |

## The `securetrace` CLI (store-based surface)

Console entrypoint: `securetrace` (or `.venv/bin/python -m securetrace`).

For the `backlog` / `lessons` / `algorithms` verbs, the **positional
argument is the store JSON path** (default `data/<kind>.json`). The doc path
defaults to the standard repo layout (`<store_dir>/../BACKLOG.md` etc.) and
is overridable with `--doc`; `--manifest` overrides `data/manifest.json`.

**Exit codes: 0 = ok, 1 = stale (diagnosed on stderr with the remediation
command), 2 = malformed file or rejected input.**

### backlog — `data/backlog.json` → `BACKLOG.md`

- `securetrace backlog upsert <store> --id B11 --title T --status OPEN
  --field NAME: LINE [--field NAME: LINE …] [--date YYYY-MM-DD]`
  — add or update an item, then commit the render. `--field` is repeatable;
  the same name appends to that field's line list.
- `securetrace backlog progress <store> --id B10 --text T
  [--date YYYY-MM-DD]` — append a progress line, then commit.
- `securetrace backlog show <store> [--id B10]` — print the store (or one
  item) as canonical JSON, verbatim (exactly one trailing newline).
- `securetrace backlog render <store>` — re-render the doc from the store
  (repairs a hand-touched doc).
- `securetrace backlog check <store>` — exit 0 in sync / 1 stale (diagnosed)
  / 2 malformed.

### lessons — `data/lessons.json` → `LESSONS_LEARNED.md`

- `securetrace lessons add <store> --title T --context C --pitfall P
  --solution S [--id LLT-NNNN] [--category …] [--severity low|medium|high]
  [--recorded YYYY-MM-DD] [--supersedes LLT-NNNN] [--prevention …]
  [--references …]` — append a lesson, then commit. `--id` defaults to the
  next free id (the old `next-id` verb is gone).
- `securetrace lessons set-intro <store> --text TEXT` — replace the
  document's intro lines (blank lines dropped), then commit the render.
- `securetrace lessons show <store> [--id LLT-0039]` — canonical JSON,
  verbatim.
- `securetrace lessons render <store>` / `securetrace lessons check
  <store>` — as above.

Category vocabulary: debugging, architecture, testing, performance,
security, dependencies, tooling, environment, process, data, other.
Severity: low, medium, high.

### algorithms — `data/registry.json` → `algorithms/INDEX.md`

- `securetrace algorithms upsert <store> --slug S --name N --version V
  --status draft|implemented|superseded --file F --summary S` — add or
  update a registry row, then commit.
- `securetrace algorithms show <store> [--slug S]` /
  `securetrace algorithms render <store>` /
  `securetrace algorithms check <store>` — as above.

### docs — all three at once

- `securetrace docs render-all [--manifest M]` — render all three docs from
  their stores (one commit per doc).
- `securetrace docs check-all [--manifest M]` — check all three; exit code
  is the worst of the three.

### migrate — one-time doc → store

- `securetrace migrate <doc.md> [--kind backlog|lessons|registry]
  [--store data/<kind>.json] [--force]` — parse a rendered (or grandfathered)
  doc into a new store, then render + commit. `--force` replaces an existing
  store. Kind is inferred from the doc basename when `--kind` is omitted.

### rmf — RMF evidence bundles (unchanged)

- `securetrace rmf build <repo-root> [--outdir DIR]` — build the dated
  SSP/SAP/SAR/POA&M bundle + canonical manifest from repository state
  (deterministic, zero network; default outdir `artifacts/rmf/<today>`).
  `make rmf-bundle` wraps it.

## scripts/ helpers (what hooks, Makefile, and CI actually call)

Hooks/Makefile/CI invoke the vendored helpers — never machine-local skill
paths (LLT-0002). The pipeline-doc surface is the store-based CLI above;
these helpers cover the remaining gate duties:

- `scripts/algorithm_index.py <doc.md> [--check]` — sync (default) or check
  (`--check`) the ALRK TSV line index inside an `algorithms/*.md` prose doc
  (exit 0 ok / 1 stale / 2 malformed); used by `make docs-check` / `make docs-render`
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

`docs-check` runs `securetrace docs check-all` (the three pipeline docs in
sync) plus `scripts/algorithm_index.py --check` per `algorithms/*.md` prose
doc (ALRK TSV indexes fresh); `docs-render` is the repair path —
`securetrace docs render-all` + the same loop in sync mode (B10 WI 10).

Useful targets: `make setup` (fresh clone: venv + pinned deps + hooks),
`make lock` (regenerate pinned hashed lockfiles), `make sbom`,
`make dependency-audit`, `make rmf-bundle`, `make docs-render` (repair
drifted docs), `make help` (everything).

## Document contracts (the parts that must stay true)

1. **Pipeline docs** (`BACKLOG.md`, `LESSONS_LEARNED.md`,
   `algorithms/INDEX.md`) — pure renders of the `data/*.json` stores; each
   carries a generated header (manual editing not permitted + the CLI path);
   canonical JSON (sorted keys, indent 2, LF, exactly one trailing newline);
   `data/manifest.json` pins `store_sha256` + `doc_sha256` + renderer
   version; mutation only via the CLI; `check` diagnoses `IN_SYNC` /
   `STORE_DRIFT` / `DOC_MODIFIED_OUTSIDE_APP` / `STORE_DRIFT_OR_DOC_DRIFT`
   / `MALFORMED_*` — see `algorithms/deterministic-doc-pipeline.md`.
2. **algorithms/ documents** — one registry row per doc (in the store); the
   row `Version` must equal the doc's `METADATA` version; doc before code,
   and doc + code land atomically; rows are never deleted (mark
   `superseded`).
3. **CONSISTENCY.md** — the consistency registry: every rule has an id
   (`CC-###`), canonical implementation, file:line locations, rationale, and
   last-updated date; every exception has a reason + approver; unregistered
   exceptions are defects; updated on every enforcement (the
   code-consistency-monitor requirement; B11 tracks the SecureTrace
   integration — deferred).
4. **.github/workflows** — pure ASCII, no duplicate mapping keys; both files
   pass `scripts/check_workflow_yaml.py` in every gate.
5. **Dependencies** — pinned + hashed (`requirements*.txt` via pip-compile);
   CI installs with `--require-hashes`; any new dependency needs a one-line
   justification in the `.in` manifest.
6. **Actions** — SHA-pinned, with the version noted in a comment.

## The agent's working loop

1. Backlog entry first (work item 1), with acceptance criteria —
   `securetrace backlog upsert`.
2. Doc cycle if an algorithm/design is involved (`algorithms/` doc first,
   registry row via `securetrace algorithms upsert`).
3. Tests RED → 4. implementation GREEN → 5. `make gate` green.
6. Conventional Commit (pre-commit gate) → 7. `git push` (pre-push gate).
8. CI green (quality + security + SonarCloud) — verify check-runs on the
   pushed sha.
9. Closeout: progress line via `securetrace backlog progress`, `check`
   green, then the next item.

Record lessons **as they are learned** (`securetrace lessons add`; dedupe
against the store first), not in a batch at the end.

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
