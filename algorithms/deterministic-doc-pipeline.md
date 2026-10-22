# Deterministic Document Pipeline (canonical store → pure render → integrity verify)

<!-- INDEX:BEGIN format=tsv version=1 -->
id	start_line	end_line
INDEX_BLOCK	3	13
METADATA	15	36
THEORY	37	136
PSEUDOCODE	137	175
WALKTHROUGH	176	215
IMPLEMENTATION	216	343
TESTS	344	362
REFERENCES	363	373
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Deterministic Document Pipeline (canonical store → pure render → integrity verify) |
| Slug | deterministic-doc-pipeline |
| Version | 0.1.8 |
| Status | draft |
| Author | SecureTrace (mirph-glitch42) |
| Created | 2026-10-20 |
| Last modified | 2026-10-22 |
| Status history | 0.1.0 (2026-10-20): initial draft (B10, documented before implementation per G1)<br>0.1.1 (2026-10-20): WI 4 — live counts corrected (10 backlog items, 5 registry rows); §5.1 lists the shared constants (`DOC_TITLES`/`CLI_VERBS`/`DEFAULT_STORE_PATHS`/`generated_header`); §5.2 rule 1 + T9 ban the top-level imports `os`/`subprocess`/`socket`/`urllib` with `integrity.py` as the documented I/O exception; T2 golden wording includes the TSV line numbers the generated header shifts<br>0.1.2 (2026-10-20): WI 5 — lessons parser/renderer implemented; §5.1 `canonical.py` lists the shared `skip_generated_header` parse-skip helper (`backlog_doc` refactored to import it; the private copy was deleted)<br>0.1.3 (2026-10-20): WI 6 — registry parser/renderer implemented; §5.1 pins the registry doc grammar (fixed six-column table, backticked slug/status, `File` cell `[<file>](<file>)` with link text equal to target, rules numbered strictly 1..N); the real `algorithms/INDEX.md` row order (`line-index-sync` before `lessons-record`) was not code-point-sorted — a violation of the file's own rule 1 — normalized as a grandfathered manual edit ahead of the T4 golden<br>0.1.4 (2026-10-20): WI 7 — `check` diagnostics implemented in `integrity.py` (pure `check_doc`, I/O wrapper `check_paths`, `check_message` naming the exact remediation command); §3 pseudocode is unchanged and normative — the T6 case (store moved after render, doc stale) diagnoses `STORE_DRIFT_OR_DOC_DRIFT`, the store-side diagnosis distinct from T5's `DOC_MODIFIED_OUTSIDE_APP`; §5.3 lists all three exit-1 diagnoses<br>0.1.5 (2026-10-21): WI 8 — CLI wiring implemented: `src/securetrace/docs/mutations.py` (pure mutation core: `upsert_backlog_item`, `append_backlog_progress`, `add_lesson`, `upsert_registry_row`, `refresh_backlog_status`) + `src/securetrace/cli_docs.py` (command layer: `_fail` / `_read_store` / `_render_line` / `_commit`, `run_*` per verb, `run_migrate`) + `src/securetrace/__main__.py` dispatch re-pointed to the store-based surface (legacy markdown-index verbs removed from the CLI; `rmf build` and the `scripts/` wrappers keep the legacy surface until B10 WI 10); §5.1 module layout updated; §5.3 gains the command-layer contract — D11 (`migrate` resolves a missing given doc path to the kind default for read + commit while printing the path as given), D13 (`show` writes the canonical JSON verbatim), D14 (the verb line prints only after a successful commit) — agent design decisions pending user review; §6 adds T11 (command-layer contract, pinned in `tests/test_cli_docs.py`); `skills/securetrace/SKILL.md` + `tests/test_skill_doc.py` re-pointed to the store-based surface (29 references)<br>0.1.6 (2026-10-21): CI remediation (D-new-8 closeout) — new contract C6 (path containment): CLI-supplied store/doc/manifest paths are validated at the command-layer boundary by `src/securetrace/docs/paths.py::resolve_within` against the workspace base; escape → `PathEscapeError` → `_fail` exit 2, no I/O, no Sonar suppressions (S8707, a 2026 LLM-security rule class; LLT-0040; CONSISTENCY CC-010); §5.1 adds `paths.py`; §6 adds T12 (escape rejection, pinned in `tests/docs/test_paths.py`, 18 tests); the S3776/S1192/S1172 refactors are command-layer internals with no contract change; S5778 pins one throwing call per `pytest.raises` body in the test suite; D-new-1…D-new-8 remain agent designs pending user review<br>0.1.7 (2026-10-22): WI 9 — real-doc migration done: `BACKLOG.md` (12 items), `LESSONS_LEARNED.md` (41 lessons), `algorithms/INDEX.md` (5 registry rows) migrated via `securetrace migrate` into `data/backlog.json` / `data/lessons.json` / `data/algorithms.json` + shared `data/manifest.json` (each `commit_render` preserves the other kinds' manifest entries); the committed docs now carry the C4 generated header (7 comment lines + blank), so the T2/T3/T4 goldens were rewritten to byte-equal roundtrip pins (`render(parse(doc)) == doc`) and the dead `strip_generated_header` / `shift_index_numbers` helpers deleted; the B10 WI 9 progress line and this doc's registry row are updated via the new CLI (dogfood, per B10 acceptance)<br>0.1.8 (2026-10-22): WI 10 — gate rewire + legacy surface removal: `make docs-check` now runs `securetrace docs check-all` (exit code = worst of the three docs) plus the per-doc ALRK TSV index loop over `algorithms/*.md` (retained `scripts/algorithm_index.py --check`); the new `make docs-render` target runs `docs render-all` plus the TSV sync loop; `scripts/backlog_index.py` + `scripts/manage_lessons.py`, the dead legacy `cli.py` verbs, and their tests are removed (the SKILL.md + consistency-registry G3 contract — "WI 10 rewires the gates to `docs check-all` and removes them"); new `lessons set-intro` verb (D15) makes the intro prose mutable only through the CLI (its rendered text referenced the deleted `manage_lessons.py`); CONSISTENCY.md exception G3 retired at this WI; §5.1 updated to the post-WI-10 layout; §6 adds T13 (set-intro contract, pinned in `tests/docs/test_mutations.py` + `tests/test_cli_docs.py`) |
| Languages | Python 3 (reference implementation); algorithm is language-agnostic |
| Implementation location | `src/securetrace/docs/` (canonical, schema, mutations, paths, backlog_doc, lessons_doc, registry_doc, integrity) + `src/securetrace/cli_docs.py` (command layer) + `src/securetrace/__main__.py` (dispatch, WI 8) + `data/` stores (`backlog.json`, `lessons.json`, `algorithms.json`, `manifest.json`, WI 9); WI 10 (gate rewire + legacy surface removal + `set_lessons_intro`, D15) landed 2026-10-22; WI 11–12 (SKILL/README/ARCHITECTURE refresh + closeout) pending |
| Time complexity | O(D) for parse, render, and check (D = document size in bytes) |
| Space complexity | O(D) — store, rendered text, and manifest held in memory at once |
| Determinism | deterministic — pure functions only: no wall clock, no randomness, no environment reads inside parse/render; entry order fixed by id/slug; canonical JSON (sorted keys, indent 2, LF, one trailing newline) |
| Dependencies | <br>Python stdlib only (`hashlib`, `json`, `pathlib`)<br>Existing cores `securetrace.backlog.index` / `securetrace.lessons.record` (structural validation of rendered output, reused) |
| Thread safety | pure core is thread-safe (no shared state); render/check/migrate commands do file I/O — caller must serialize |
| Related documents | <br>`algorithms/line-index-sync.md` (the TSV index blocks the renderer emits and the parser consumes)<br>`algorithms/lessons-record.md` (the lesson-entry grammar the lessons renderer/parser implements)<br>`algorithms/rmf-evidence-bundle.md` (consumer of the rendered docs; shares the canonical-JSON + no-clock discipline) |

<!-- SECTION:THEORY -->
## 2. Theory

### 2.1 Problem definition

The three pipeline documents — `BACKLOG.md`, `LESSONS_LEARNED.md`,
`algorithms/INDEX.md` — are the audit trail of an agent-built system. Before
B10 they were *authored* files: an agent (or human) edited the markdown
directly and a script only verified the embedded line index. A hand edit was
indistinguishable from a CLI update, and the document bytes had no canonical
data version they could be verified against.

The pipeline inverts this. A repo-local **store** (canonical JSON under
`data/`) becomes the single source of truth; the document is a **pure render**
of that store:

```
render : Store → DocBytes                              (pure, deterministic)
parse  : DocBytes → Store                              (inverse of render on well-formed docs)
check  : (Store, DocBytes, Manifest) → IN_SYNC | STALE(kind) | MALFORMED
```

Contract (guaranteed):

- **C1 (determinism):** `render(store)` is byte-identical across runs,
  machines, and moments in time — the renderer reads no clock, no randomness,
  no environment.
- **C2 (lossless roundtrip):** `parse(render(store)) == store` and
  `render(parse(doc)) == render(store)` for every well-formed doc.
- **C3 (tamper detection):** `check` distinguishes (a) the doc was modified
  outside the app, (b) the store was modified after the last render, (c) the
  store or manifest is malformed — each with a different diagnosis and exit
  code.
- **C4 (CLI-only mutation):** the store and the document are written only by
  `securetrace` commands; every rendered doc carries a generated header
  warning that manual editing is not permitted.
- **C5 (no clock):** the only dates in a document are *data* fields (e.g.
  lesson `Recorded`, the store's `updated` date) — never renderer output.
- **C6 (path containment):** every CLI-supplied path (store, doc,
  manifest) is validated against the workspace base by one command-layer
  helper (`docs/paths.py::resolve_within`) before any I/O; a path that
  would escape the base is rejected with a diagnostic and exit 2 — the
  core never sees an uncontained path (one boundary, not per-sink checks).

Precondition: the store file is readable canonical JSON (else `MALFORMED`,
exit 2). Undefined: none — behavior on missing/malformed inputs is specified
(§3, §5.3). Forbidden: writing a document without also updating the manifest;
re-sorting open prose lists (progress lines are data, not derived).

### 2.2 Why this approach

- **Canonical JSON store + pure render (chosen).** The document becomes a
  function of data; verification is a byte comparison; RMF evidence can cite
  `sha256(store)` as the version of record; structured data enables future
  report generation without re-parsing prose.
- **Rejected — keep authoring markdown, add a hash header line inside the
  doc.** A hash line cannot cover itself (self-reference), and it still
  permits hand edits anywhere else in the file.
- **Rejected — git-only provenance.** Git records *who/when*, not *whether the
  content is a function of the store*; it cannot diagnose "doc modified
  outside the app".
- **Rejected — fully structured fields for every prose cell.** Closed-vocabulary
  cells (status, priority, lesson fields, registry columns) become structured
  data; open prose (request verbatim, problem, progress lines, closeout lines)
  stays as *ordered line lists* in the store. This keeps roundtrips lossless
  for the live 10 backlog items and 34 lessons (at WI 4 time; the record is append-only and grows with B10) without inventing a prose schema.

### 2.3 Correctness argument

- Canonical JSON is a bijection between a validated store object and a unique
  byte sequence (keys sorted, indent fixed, LF endings, one trailing newline)
  — so `sha256(store_bytes)` uniquely identifies the store.
- `render` is pure (input: the store; no I/O, no clock, no randomness) and
  orders entries by stable id — so `render(store)` is unique; its sha256
  identifies the expected document.
- `check` compares actual doc bytes against `render(store)`:
  - equal → in sync (manifest must agree, else `STORE_DRIFT`);
  - unequal → someone touched the doc or the store after the last render.
    The manifest pins `store_sha256` *at render time*: if it equals
    `sha256(current store)` the store is unchanged since render, so the doc
    must have been modified outside the app (case a); otherwise the store
    moved (case b) — the message names the remediation command.
  - store fails schema validation → case c (exit 2), before any comparison.
- Losslessness: `parse` accepts exactly the grammar `render` emits (plus the
  grandfathered current files, which differ only by the absent generated
  header — and the TSV line numbers that header shifts); the golden
  roundtrip tests (T2–T4) pin `parse ∘ render = id` on the live data, so
  migration cannot silently drop a field.

### 2.4 Complexity

Single scans throughout: parse O(D), render O(D) (two passes — body, then the
index line numbers over the final text), check O(D) (one render + one byte
compare + two sha256 over ≤ 2·D bytes). No quadratic passes. Behavioral
verification (golden bytes), not timing.

### 2.5 Deviations

none — documented before implementation.

<!-- SECTION:PSEUDOCODE -->
## 3. Pseudocode

```
CANONICAL_JSON(store):
  return json_dumps(store, sort_keys = true, indent = 2, ensure_ascii = false) + "\n"
  # unique byte form: key order fixed by sort, LF line endings, exactly one trailing newline

RENDER_DOC(store, doc_kind) -> text:
  head   := TITLE_LINES[doc_kind]                         # constant, in code
  head   += GENERATED_HEADER[doc_kind, renderer_version]  # constant; no-hand-edit warning + CLI path
  body   := BODY_LINES(doc_kind, store)                   # pure; entries sorted by id/slug
  index  := INDEX_BLOCK(doc_kind, head + body)            # line numbers computed over the final layout
  return join(head + index + body, "\n") + "\n"           # unique for a given store

PARSE_DOC(doc_bytes, doc_kind) -> store:
  text := utf8_decode(doc_bytes)                          # failure -> MALFORMED
  strip TITLE_LINES (exact prefix) and GENERATED_HEADER (optional: absent on grandfathered docs)
  require exactly one well-formed index block; recompute it; mismatch -> MALFORMED
  split remaining text by the doc_kind section markers
  per section: extract closed-vocabulary cells into fields, open prose into ordered line lists
  validate: id uniqueness, id ordering, closed vocabularies, required fields
  return store

CHECK(store_path, doc_path, manifest) -> (exit_code, diagnosis):
  store := load_and_validate(store_path)                  # failure -> (2, MALFORMED_STORE)
  expected := RENDER_DOC(store)
  actual  := read(doc_path)                               # missing -> (2, DOC_MISSING)
  if actual == expected:
      if manifest[doc].store_sha256 == sha256(CANONICAL_JSON(store))
         and manifest[doc].doc_sha256  == sha256(expected):
          return (0, IN_SYNC)
      return (1, STORE_DRIFT)                             # store changed after render -> run render
  # actual != expected:
  if manifest[doc].store_sha256 == sha256(CANONICAL_JSON(store)):
      return (1, DOC_MODIFIED_OUTSIDE_APP)                # store unchanged -> the doc was touched
  return (1, STORE_DRIFT_OR_DOC_DRIFT)                    # both may have moved -> render, re-check
```

<!-- SECTION:WALKTHROUGH -->
## 4. Walk-through (plain English)

### 4.1 Step-by-step

1. The agent decides a change (e.g. "append a progress line to B10") and
   expresses it as CLI input — a structured command carrying data, never a
   file edit.
2. The CLI loads the store (JSON), applies the validated mutation, and writes
   the store back in canonical form (sorted keys, indent 2, trailing newline).
3. `render` — run by the same command or explicitly — computes the document
   text from the store alone: constants from code, data from the store,
   entries in id order, index line numbers recomputed over the final layout.
4. The rendered bytes are written atomically (temp file + rename), and the
   manifest records `sha256(store)` + `sha256(rendered)` + renderer version.
5. At commit time the gate re-runs `check`: re-render the store, byte-compare
   with the file on disk, cross-check the manifest. Equal → in sync. Unequal →
   the manifest discriminates whether the doc or the store moved, and the
   stderr message names the exact remediation command.

### 4.2 Worked example

Store: the one-item backlog store of test T1 (§6).

- `RENDER_DOC` emits: `# Backlog`, blank, the generated header (a 7-line
  `<!-- … -->` block carrying the no-hand-edit warning and the CLI path),
  blank, the TSV index block (lines computed over this exact layout), blank,
  the `## Status` header section, the queue section, one
  `<!-- BACKLOG:ITEM:B1 -->` item with all of its fields, and the constraints
  section — then one trailing newline.
- `PARSE_DOC` strips the title and the optional header, verifies the index
  block, splits by section markers, and fills
  `{updated, items: [B1 with all fields], constraints: […]}` — byte-identical
  data to the input store (C2).
- Tamper: flip one byte in the committed doc (change `**B1**` to `**B2**` in
  the status line). `CHECK` re-renders, byte-compares → mismatch; the
  manifest's `store_sha256` equals `sha256` of the current store → diagnosis
  `DOC_MODIFIED_OUTSIDE_APP`, exit 1, commit blocked, message says: update the
  store via the CLI, then `securetrace backlog render`.

<!-- SECTION:IMPLEMENTATION -->
## 5. Implementation notes (entry-level guide)

### 5.1 Module layout (B10)

- `src/securetrace/docs/__init__.py` — package doc + `RENDERER_VERSION` constant.
- `src/securetrace/docs/canonical.py` — `canonical_json`, `sha256_hex`,
  `skip_generated_header` (the shared C4 parse-skip, used by the backlog and
  lessons renderers), and the per-kind constants the renderers share:
  `DOC_TITLES`, `CLI_VERBS`, `DEFAULT_STORE_PATHS`, `generated_header`
  (the 7-line C4 no-hand-edit block).
- `src/securetrace/docs/schema.py` — store validation (backlog/lessons/registry) + typed errors.
- `src/securetrace/docs/backlog_doc.py` — `parse_backlog` / `render_backlog`.
- `src/securetrace/docs/lessons_doc.py` — `parse_lessons` / `render_lessons`.
- `src/securetrace/docs/registry_doc.py` — `parse_registry` / `render_registry`.
  The registry doc is a markdown table, not a TSV-indexed doc: title, blank,
  generated header, blank, the intro blockquote lines, blank, the fixed
  six-column table (`Slug`/`Name`/`Version`/`Status`/`File`/`One-line
  summary` header + `|---|…|` separator + one row per algorithm), blank,
  `## Rules` + the rule lines numbered strictly 1..N. Row cell grammar: the
  slug and status are backticked, the `File` cell is `[<file>](<file>)` with
  link text equal to the target (the relative .md path), the three prose
  cells are plain; a row cell containing ` | ` is unparseable by construction
  (the split must yield exactly six cells).
- `src/securetrace/docs/integrity.py` — manifest model + `check` diagnostics.
- `src/securetrace/docs/mutations.py` — pure mutation core (no I/O, no
  clock): `upsert_backlog_item`, `append_backlog_progress`, `add_lesson`,
  `set_lessons_intro` (WI 10, D15), `upsert_registry_row` (each `store →
  store`, validated by `schema` before and after), plus
  `refresh_backlog_status` (derives the `**Queue** / **In progress** /
  **Done**` line from item statuses) and the id/slug helpers
  (`_next_lesson_id`, `_sorted_slug_index`).
- `src/securetrace/docs/paths.py` — C6 path containment:
  `PathEscapeError` (a `ValueError`) + `resolve_within(raw, base)`; pure
  pathlib, no `os` (T9-clean); the command layer resolves every
  CLI-supplied path through it and maps `PathEscapeError` to `_fail`
  (exit 2) — one boundary, not per-sink checks.
- `src/securetrace/cli_docs.py` — the command layer (C4 boundary): `_fail`
  (stderr `securetrace: {msg}` + exit 2), `_read_store` / `_StoreReadError`,
  the single `_render_line` success-line helper, `_commit` (store → doc →
  manifest via `integrity.commit_render`), `run_*` for every verb, and
  `run_migrate`. The wall clock is allowed **only here** (date defaults),
  never in the core.
- `src/securetrace/__main__.py` — dispatch, re-pointed in WI 8:
  `backlog`/`lessons`/`algorithms` → `cli_docs` (positional = store path),
  plus `docs render-all|check-all` and `migrate`; `rmf build` → legacy
  `cli.run_rmf_build`. The legacy markdown-index verbs are gone from the CLI
  (argparse rejects them, exit 2).
- `src/securetrace/cli.py` — the RMF command layer (`run_rmf_build`, the
  shared `_fail` exit-2 vocabulary); the legacy markdown-index verbs were
  removed from the CLI dispatch in WI 8 and the last remaining surface
  (`scripts/backlog_index.py` + `scripts/manage_lessons.py` wrappers + the
  dead `run_*` verbs + their tests) was deleted in WI 10.
- `tests/docs/` — mirrors the package (`test_mutations.py`, golden fixtures
  in `tests/fixtures/docs/`); `tests/test_cli_docs.py` pins the command
  layer (T11, T13); `tests/test_cli.py` pins the `rmf build` + dispatch
  contracts (the legacy-surface tests were removed in WI 10);
  `tests/scripts/test_skill_scripts.py` pins the retained `scripts/` tools
  (the ALRK `algorithm_index.py` TSV tool).

### 5.2 Determinism rules (each enforced by a test)

1. No top-level imports of `datetime`, `time`, `random`, `uuid`, `os`,
   `subprocess`, `socket`, or `urllib` in the `securetrace.docs` core modules
   (AST-asserted, same discipline as the RMF offline test T-C3); `integrity.py`
   is the documented exception — the manifest I/O module (temp file +
   `os.replace`).
2. Entries iterate in stable-id order; open prose lists (progress, closeout,
   work items, acceptance) are data — emitted in stored order, never re-sorted.
3. All output uses `\n`; every rendered file ends with exactly one trailing
   newline; canonical JSON ends with exactly one trailing newline.
4. `RENDERER_VERSION` is a code constant; the generated header and the manifest
   both carry it; changing it changes expected bytes (tests pin both).
5. File writes are atomic (temp file in the target directory + `os.replace`).

### 5.3 CLI contract (exit codes 0/1/2)

- `upsert` / `progress` / `add` / `show` / `render` / `migrate`: 0 ok;
  2 rejected input (schema violation, missing store, id collision, store
  already present without `--force` on `migrate`).
- `check`: 0 in sync; 1 stale — `DOC_MODIFIED_OUTSIDE_APP`, `STORE_DRIFT`,
  or `STORE_DRIFT_OR_DOC_DRIFT` (diagnosis + remediation command on stderr);
  2 malformed (store, manifest, or doc unreadable/missing).
- `render` and `check` compute expected bytes the same way — one `RENDER_DOC`
  on the same loaded store — so they can never disagree.
- The positional file argument of the re-pointed `backlog` / `lessons` /
  `algorithms` commands is the **store** path; the document path defaults to
  the standard repo layout (`<store_dir>/../BACKLOG.md` etc.) and is
  overridable with `--doc`.

Command-layer behavior (WI 8; D11/D13/D14 are agent design decisions pending
user review — flagged here and in the status history):

- **D11 (migrate resolution):** if the given doc path does not exist but the
  kind's default doc path does (from the repo root a user types
  `migrate INDEX.md` for `algorithms/INDEX.md`), the default is used for
  the read *and* the render commit; both printed lines (migrate line +
  render line) carry the path **as given** (`tests/test_cli_docs.py::test_migrate_registry_rows` pins it).
- **D13 (verbatim show):** `show` writes `canonical_json(store)` — or one
  item/lesson/row — with `sys.stdout.write`, exactly one trailing newline,
  no `print`-added newline, no reformatting.
- **D14 (print after commit):** the verb success line (`upsert: …`,
  `progress: …`, `add: …`, `render: …`) is printed only after the store +
  doc + manifest commit succeeds; a failed commit prints the stderr line and
  nothing else.
- **D15 (intro via CLI, WI 10):** the lessons store's `intro` prose is
  mutable only through `lessons set-intro <store> --text TEXT` — the pure
  mutation `set_lessons_intro` (non-empty list of non-empty, tab-free lines,
  schema-validated) commits through the shared `_commit` path, then prints
  the verb line `intro: updated ({store})` + the shared render line (D14).
  Rationale: the rendered LESSONS intro referenced the now-deleted
  `scripts/manage_lessons.py`; keeping the intro mutable only through the
  store preserves the B10 invariant that every pipeline-doc mutation is
  expressible via the `securetrace` CLI.

**Gate wiring (WI 10).** One definition, three enforcement points (the
Makefile target, `hooks/pre-commit` stage 3, and the CI `quality` step all
invoke the same target):

- `make docs-check` — `securetrace docs check-all` (exit code = the worst of
  the three doc checks; 0 in sync / 1 drift / 2 malformed) **plus** the
  per-doc ALRK TSV index check: `scripts/algorithm_index.py <doc> --check`
  over every `algorithms/*.md` except `INDEX.md` (the prose docs are
  agent-written; their TSV index stays the ALRK skill's tool).
- `make docs-render` (new in WI 10) — `securetrace docs render-all` **plus**
  the TSV sync loop: `scripts/algorithm_index.py <doc> sync` over the same
  prose docs; idempotent when the index is already fresh.

<!-- SECTION:TESTS -->
## 6. Tests

| # | Sample input (abridged) | Expected output | Why it matters |
|---|---|---|---|
| T1 | one-item backlog store (B1, 2 progress lines, 3-line closeout) | `render(parse(render(store))) == render(store)`; sha256 identical across two runs | C1/C2 core roundtrip |
| T2 | the real repo `BACKLOG.md` (10 items at B10 time) | `parse → render` reproduces committed bytes (modulo the generated header block and the TSV line numbers it shifts); 10/10 items, all fields | lossless migration of the live backlog |
| T3 | the real repo `LESSONS_LEARNED.md` (34 lessons at WI 4 time; the test derives N from the live file, never a hardcoded count) | roundtrip identity; N/N lessons, closed vocabularies intact | lossless migration of the live record |
| T4 | the real repo `algorithms/INDEX.md` (5 rows) | roundtrip identity; 5/5 rows in slug order | lossless migration of the registry |
| T5 | T1 doc with one byte flipped inside an item body | `check` exit 1; stderr names the outside-app diagnosis + the render command | user requirement 2 — tamper is diagnosed, not just detected |
| T6 | T1 store edited (progress line appended) after render | `check` exit 1; diagnosis is store drift, distinct from T5 | the two drift directions are told apart |
| T7 | store with duplicate item id `B1` | mutation/check exit 2, malformed-store diagnosis | schema gate before any render |
| T8 | `canonical_json({"b": 1, "a": {"d": 2, "c": 3}})` | `{\n  "a": {\n    "c": 3,\n    "d": 2\n  },\n  "b": 1\n}\n` | the canonical byte form is unique (T8 pins sorted keys, indent 2, trailing newline) |
| T9 | source of the `securetrace.docs` core modules (discovered dynamically; `integrity.py` excluded) | AST: no top-level imports of `datetime`/`time`/`random`/`uuid`/`os`/`subprocess`/`socket`/`urllib` | no-clock/no-env discipline (C5) |
| T10 | same store with items in different JSON order | rendered output identical | ordering comes from the id, never from input order |
| T11 | command layer (D11/D13/D14): `migrate INDEX.md` with the store absent; `show` after a mutation; a mutation verb whose commit fails | migrate resolves to `algorithms/INDEX.md` for read + commit but prints `migrate: N rows from INDEX.md → …`; `show` stdout is byte-equal to `canonical_json` (one trailing `\n`); on commit failure the verb line is absent and the stderr line present | the user-facing CLI contract is part of the algorithm's guarantee, not an afterthought — pinned in `tests/test_cli_docs.py` |
| T12 | a CLI-supplied path that escapes the workspace base (`../data/x.json`; an absolute path outside the repo) as any store/doc/manifest argument | `resolve_within` raises `PathEscapeError` (a `ValueError`); the command layer maps it to the `securetrace: …` stderr line, exit 2, no I/O; a relative path inside the base passes unchanged | C6 — the trust boundary is one helper at the CLI edge (S8707), pinned in `tests/docs/test_paths.py` (18 tests) |
| T13 | `set_lessons_intro` on a one-lesson store: (a) a two-line intro → new store, lessons untouched, schema-valid; (b) `[]`, `[""]`, `["a\tb"]` → `InvalidInput`; `run_lessons_set_intro` happy path → rendered LESSONS carries the new intro, stdout = `intro: updated ({store})` + the render line, exit 0 | the intro prose is mutable only via the CLI (D15) — no dangling reference to the deleted script, no hand-edited stores; pinned in `tests/docs/test_mutations.py` + `tests/test_cli_docs.py` |

<!-- SECTION:REFERENCES -->
## 7. References

- B10 backlog entry (BACKLOG.md) — requirements verbatim, scope decision, acceptance criteria.
- `algorithms/line-index-sync.md` — the TSV index-block grammar the renderer emits and the parser verifies.
- `algorithms/lessons-record.md` — the lesson-entry grammar (fields, vocabularies, exit model).
- `algorithms/rmf-evidence-bundle.md` — canonical-JSON + no-clock precedent this pipeline shares.
- LLT-0009 (priority-line parsing), LLT-0012 (scan-window off-by-one) — parser edge cases already hit by the legacy cores; the new parser must not regress them.
- `tests/test_cli_docs.py` — command-layer contract (D11/D13/D14, T11); 53 tests at v0.1.5.
- `skills/securetrace/SKILL.md` + `tests/test_skill_doc.py` — the agent-facing surface this pipeline defines (29 pinned references at v0.1.5).
- `docs/dow-requirements.md` — DoD RMF / SWP config-management context for why the audit trail must be verifiable.
