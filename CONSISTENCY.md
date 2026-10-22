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
| CC-001 | CLI error surfacing | one `_fail(prog, msg)` helper: `securetrace: {msg}` to stderr, exit 2; every error path is `return _fail(...)` | `src/securetrace/cli_docs.py:115`, `src/securetrace/cli.py:81` | G3 (legacy surface) | single error vocabulary and exit code; error paths cannot exit 0; pinned by tests/test_cli.py + tests/test_cli_docs.py | 2026-10-21 |
| CC-002 | verb success line | after a successful commit only: one `verb: …` line, then the shared render line (D14) | `src/securetrace/cli_docs.py:253,294,413,493,743` | G3 (legacy surface) | D14 (ALRK v0.1.6 §5.3); pinned by the single-capture capsys assertions in tests/test_cli_docs.py (LLT-0039) | 2026-10-21 |
| CC-003 | render summary line | the shared `_render_line(doc, sp, man)` builds every post-mutation render line; no inline variants | `src/securetrace/cli_docs.py:188` (used at `:254,295,414,494,562,620,744`) | None | one helper, one wording — drift is impossible | 2026-10-21 |
| CC-004 | store read + malformed store | one `_read_store` raising `_StoreReadError`; callers map it to `_fail` (exit 2) | `src/securetrace/cli_docs.py:121` (error type `:108`) | None | every read path shares one failure vocabulary; pinned by the malformed-store tests in tests/test_cli_docs.py | 2026-10-21 |
| CC-005 | mutation commit | every store mutation commits through `_commit` → `integrity.commit_render` (store + doc + manifest, re-verified) | `src/securetrace/cli_docs.py:193` (used at `:249,291,409,489,559,617,736`) | None | no mutation path hand-writes store/doc/manifest; B10 acceptance; pinned by tests/docs/test_integrity.py + tests/test_cli_docs.py | 2026-10-21 |
| CC-006 | `show` output | verbatim `sys.stdout.write(canonical.canonical_json(...))` — never `print`, never reformatted | `src/securetrace/cli_docs.py:327,330,443,446,523,526` | None | D13 (ALRK v0.1.6 §5.3); machine-readable stdout; pinned by tests/test_cli_docs.py | 2026-10-21 |
| CC-007 | wall clock | `datetime.date.today()` only in the command layer; core modules are clock-free | `src/securetrace/cli_docs.py:360`, `src/securetrace/cli.py:274,386`, `src/securetrace/__main__.py:230,240` | None | T9 AST guard: tests/docs/test_core_discipline.py:39 (`test_core_modules_import_no_clock_randomness_or_env`) | 2026-10-21 |
| CC-008 | date format | ISO `YYYY-MM-DD` via `.isoformat()` at every clock anchor; stores carry ISO dates only | `src/securetrace/cli_docs.py:360`, `src/securetrace/cli.py:274,386`, `src/securetrace/__main__.py:230,240` | None | deterministic renders + RMF evidence dates; pinned by tests/docs/test_schema.py | 2026-10-21 |
| CC-009 | argparse surface | shared `_store_options` / `_render_check` build the store positional and the render/check verbs for every doc kind | `src/securetrace/__main__.py:64,70` (used at `:74,79,99,106,112,132,138,155,161`) | None | one CLI grammar across backlog/lessons/registry verbs; pinned by tests/test_cli_docs.py | 2026-10-21 |
| CC-010 | path containment | one `docs/paths.py::resolve_within(raw, base)` + `PathEscapeError` (a `ValueError`); the command layer resolves every CLI-supplied path before any I/O and maps `PathEscapeError` → `_fail` (exit 2) | `src/securetrace/docs/paths.py:24,28`; `src/securetrace/cli_docs.py:172-174,185,316,432,512,666,675,678` (import `:61`) | G3 (legacy surface) | C6 / S8707 (2026 LLM-security rule class) boundary fix — LLT-0040; pinned by `tests/docs/test_paths.py` (18 tests) | 2026-10-21 |

## Exceptions

| Date | Rule ID | Surface | Deviation | Reason | Approved by |
|------|---------|---------|-----------|--------|-------------|
| 2026-10-21 | CC-001…CC-010 | legacy `securetrace.cli` + `scripts/{backlog_index,manage_lessons,algorithm_index}.py` wrappers | the legacy .md-editing surface (own verb lines, `backlog sync` etc.) coexists with the store-based surface during the B10 WI 8→10 transition | user-approved B10 scope: legacy verbs are rejected at the new dispatch but kept as thin `scripts/` wrappers until WI 10 removes them and the gates re-point (exception G3 of the B10 closeout); **expires at B10 WI 10** | Joshua Murphy (user) |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-10-21 | registry created; CC-001…CC-009 adopted (every location verified file:line against the B10 WI 8 closeout); exception G3 (dual surface) registered | Joshua Murphy (user request — code-consistency-monitor adopted as a project requirement); agent drafted the rule set |
| 2026-10-21 | CC-010 (path containment — C6 / S8707, `docs/paths.py::resolve_within`, LLT-0040) added; every CC-001…CC-010 location re-verified file:line against the post-Sonar-remediation code (commits `650a466`, `8606918`, `8a0c236`); G3 extended to CC-010 (the legacy `scripts/` wrappers also take file paths without containment) | agent (D-new-8 closeout); rule + anchors pending user review |
| 2026-10-21 | CC-002/CC-003/CC-005/CC-010 `cli_docs.py` anchors re-derived after the S3776 `run_migrate` split (new private helpers `_migrate_targets` / `_migrate_source`; containment calls now at `:666,675,678`); behavior-identical, gate green (408 tests) | agent (S3776 closeout) |
