# Consistency Registry

| Field | Value |
|-------|-------|
| Project | SecureTrace |
| Owner | Joshua Murphy |
| Last full review | 2026-10-21 |

The registry is the project's source of truth for what "consistent" means.
It is maintained per the code-consistency-monitor skill (every rule has a
stable `CC-###` ID; locations are file:line; exceptions carry a reason and an
approver; new capabilities get a rule the moment they appear on a second
surface; rules are superseded in the change log, never deleted). Re-verify
all rules against the code at least quarterly or after any major refactor,
then update `Last full review`.

## Rules

| ID | Capability | Canonical implementation | Locations | Exceptions | Rationale | Last updated |
|----|------------|--------------------------|-----------|------------|-----------|--------------|
| CC-001 | CLI error surfacing | one `_fail(prog, msg)` helper: `securetrace: {msg}` to stderr, exit 2; every error path is `return _fail(...)` | `src/securetrace/cli_docs.py:108`, `src/securetrace/cli.py:81` | G3 (legacy surface) | single error vocabulary and exit code; error paths cannot exit 0; pinned by tests/test_cli.py + tests/test_cli_docs.py | 2026-10-21 |
| CC-002 | verb success line | after a successful commit only: one `verb: …` line, then the shared render line (D14) | `src/securetrace/cli_docs.py:231,272,388,465,677` | G3 (legacy surface) | D14 (ALRK v0.1.5 §5.3); pinned by the single-capture capsys assertions in tests/test_cli_docs.py (LLT-0039) | 2026-10-21 |
| CC-003 | render summary line | the shared `_render_line(doc, sp, man)` builds every post-mutation render line; no inline variants | `src/securetrace/cli_docs.py:166` (used at `:232,273,389,466,531,585,677`) | None | one helper, one wording — drift is impossible | 2026-10-21 |
| CC-004 | store read + malformed store | one `_read_store` raising `_StoreReadError`; callers map it to `_fail` (exit 2) | `src/securetrace/cli_docs.py:114` (error type `:101`) | None | every read path shares one failure vocabulary; pinned by the malformed-store tests in tests/test_cli_docs.py | 2026-10-21 |
| CC-005 | mutation commit | every store mutation commits through `_commit` → `integrity.commit_render` (store + doc + manifest, re-verified) | `src/securetrace/cli_docs.py:171` (used at `:227,269,384,461,528,582,669`) | None | no mutation path hand-writes store/doc/manifest; B10 acceptance; pinned by tests/docs/test_integrity.py + tests/test_cli_docs.py | 2026-10-21 |
| CC-006 | `show` output | verbatim `sys.stdout.write(canonical.canonical_json(...))` — never `print`, never reformatted | `src/securetrace/cli_docs.py:302,305,415,418,492,495` | None | D13 (ALRK v0.1.5 §5.3); machine-readable stdout; pinned by tests/test_cli_docs.py | 2026-10-21 |
| CC-007 | wall clock | `datetime.date.today()` only in the command layer; core modules are clock-free | `src/securetrace/cli_docs.py:335`, `src/securetrace/cli.py:274,386`, `src/securetrace/__main__.py:227,237` | None | T9 AST guard: tests/docs/test_core_discipline.py:39 (`test_core_modules_import_no_clock_randomness_or_env`) | 2026-10-21 |
| CC-008 | date format | ISO `YYYY-MM-DD` via `.isoformat()` at every clock anchor; stores carry ISO dates only | `src/securetrace/cli_docs.py:335`, `src/securetrace/cli.py:274,386`, `src/securetrace/__main__.py:227,237` | None | deterministic renders + RMF evidence dates; pinned by tests/docs/test_schema.py | 2026-10-21 |
| CC-009 | argparse surface | shared `_store_options` / `_render_check` build the store positional and the render/check verbs for every doc kind | `src/securetrace/__main__.py:51,59` (used at `:63,68,88,95,101,121,127,144,150`) | None | one CLI grammar across backlog/lessons/registry verbs; pinned by tests/test_cli_docs.py | 2026-10-21 |

## Exceptions

| Date | Rule ID | Surface | Deviation | Reason | Approved by |
|------|---------|---------|-----------|--------|-------------|
| 2026-10-21 | CC-001…CC-009 | legacy `securetrace.cli` + `scripts/{backlog_index,manage_lessons,algorithm_index}.py` wrappers | the legacy .md-editing surface (own verb lines, `backlog sync` etc.) coexists with the store-based surface during the B10 WI 8→10 transition | user-approved B10 scope: legacy verbs are rejected at the new dispatch but kept as thin `scripts/` wrappers until WI 10 removes them and the gates re-point (exception G3 of the B10 closeout); **expires at B10 WI 10** | Joshua Murphy (user) |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-10-21 | registry created; CC-001…CC-009 adopted (every location verified file:line against the B10 WI 8 closeout); exception G3 (dual surface) registered | Joshua Murphy (user request — code-consistency-monitor adopted as a project requirement); agent drafted the rule set |
