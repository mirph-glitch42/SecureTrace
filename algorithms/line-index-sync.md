# Line-Index Sync (marker scan, delta computation, idempotent TSV rewrite)

<!-- INDEX:BEGIN format=tsv version=1 -->
id	start_line	end_line
INDEX_BLOCK	3	13
METADATA	15	37
THEORY	38	180
PSEUDOCODE	181	256
WALKTHROUGH	257	304
IMPLEMENTATION	305	388
TESTS	389	428
REFERENCES	429	438
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Line-Index Sync (marker scan, delta computation, idempotent TSV rewrite) |
| Slug | line-index-sync |
| Version | 0.1.3 |
| Status | backfilled |
| Author | SecureTrace bootstrap (mirph-glitch42) |
| Created | 2026-10-18 |
| Last modified | 2026-10-19 |
| Status history | 0.1.0 (2026-10-18): backfilled from `ad0fc9f`<br>0.1.1 (2026-10-19): `find_sections` marker match described as two alternation-free regexes + reserved-kind validation — behavior-identical (B7 increment 4)<br>0.1.2 (2026-10-19): `PRIORITY_RE` value pattern described in the linear non-lazy form (`.+`; the consumer strips before the map lookup and the error text, so the capture is bit-identical) — behavior-identical (B7 increment 7)<br>0.1.3 (2026-10-19): `PRIORITY_RE` value pattern described as a single non-whitespace token `(\S+)` with a trailing `\s*$` after the live API kept flagging `.\+` — unpinned degenerate inputs (whitespace-only or multi-word values) now index as `Low` instead of erroring (B7 increment 8) |
| Pinned to | `mirph-glitch42/SecureTrace@ad0fc9f` (2026-10-18) |
| Languages | Python 3 (reference implementation); algorithm is language-agnostic |
| Implementation location | <br>`scripts/backlog_index.py:L51-L237` (reference implementation, richest format)<br>`scripts/algorithm_index.py:L38-L150` (same core, `id/start_line/end_line` format)<br>`scripts/manage_lessons.py:L334-L390` (same delta core, third format — see `lessons-record`) |
| Time complexity | O(L) per operation (L = physical line count) — observed, matches ideal |
| Space complexity | O(L) for `sync` (new line list + rewritten text); O(S) for row model (S = section count) |
| Determinism | deterministic |
| Dependencies | none (Python stdlib `re` only) |
| Thread safety | pure core is thread-safe (no shared state); file I/O is caller-serialized |
| Related documents | <br>`algorithms/lessons-record.md` (applies the same delta core to the lessons format)<br>`LESSONS_LEARNED.md` entry LLT-0002 (why the scripts are vendored) |

<!-- SECTION:THEORY -->
## 2. Theory

### 2.1 Problem definition

A markdown record file (BACKLOG.md, an algorithm document, or a lessons record)
carries a **self-describing index block**: a TSV table delimited by
`<!-- INDEX:BEGIN … -->` / `<!-- INDEX:END -->` markers that lists the line
range of every section (or entry) in the *same* file. The first row always
describes the block itself, so the index is inclusive of itself.

The core difficulty: the block's own size depends on how many sections it must
list, and inserting that block shifts every section below it. Line numbers
computed *before* the rewrite are therefore wrong. The algorithm must compute
the block content so that **every reported line number is correct for the file
after the rewrite**, and do so in one pass (no fixed-point iteration), while
keeping the operation **idempotent**: `sync(sync(t)) == sync(t)` and
`check(sync(t))` passes.

Formal contract (reference implementation, backlog variant):

- **Input:** text `t` of `L` lines containing (a) an index block at 0-indexed
  lines `b < e` (interior `b+1 … e−1`), and (b) one or more section markers
  (backlog: `<!-- BACKLOG:HEADER|QUEUE|CONSTRAINTS|ITEM:<ID> -->`,
  `<ID> ∈ [A-Z][A-Z0-9_]*`; algorithm: `<!-- SECTION:<ID> -->`,
  `<ID> ∈ [A-Z0-9_]+`), all located strictly after line `e`.
- **Output (`sync`):** text `t'` identical to `t` except the block interior is
  replaced by `1 + S` lines (one TSV header + one row per section). Nothing
  outside `(b, e)` is touched.
- **Output (`check`):** pass iff the stored interior equals the computed
  interior; otherwise *stale*.
- **Errors (exit 2):** missing block, empty block, marker at or inside the
  block, duplicate marker id, reserved item id (`HEADER`/`QUEUE`/`CONSTRAINTS`
  as an item id), zero sections, out-of-vocabulary priority.
- **Forbidden:** editing the TSV by hand; sections before the block.
- **Undefined:** behavior on non-UTF-8 input (the reference reads as UTF-8 and
  raises).

### 2.2 Why this approach

**Chosen: closed-form single-delta computation.** The rewrite changes exactly
one contiguous region (the block interior), and every section lies *after*
that region. Hence every section's line number shifts by one constant
`delta = new_interior − old_interior`. Reported line number = original line
number + `delta`; the block's own end line is `b + new_interior + 1`
(0-indexed). One pass suffices.

**Rejected: iterative fixed point** — write the block, re-scan, recompute,
repeat until stable. It needs a termination argument, can oscillate if the
block size is computed from stale geometry, and costs O(k) full scans.
Unnecessary because the geometry is a single contiguous shift.

**Rejected: store pre-rewrite numbers and adjust the INDEX_BLOCK row
separately.** Fragile: the block's own row depends on the final block size,
so the adjustment is exactly the delta computation in disguise, split across
two places.

**Rejected: byte offsets instead of line numbers.** Survives line-join
differences but breaks the human-readable contract (reviewers read line
numbers in CI output and hooks).

### 2.3 Correctness argument

Invariant **I1 (single shift):** `sync` replaces exactly the lines
`b+1 … e−1` and leaves lines `≤ b` and `≥ e` in place *within the original
file*. In the rewritten file, the END marker sits at 0-indexed position
`b + 1 + (1 + S)` and every section marker `s > e` sits at `s + delta`, where
`delta = (b + new_interior + 1) − e = new_interior − old_interior`
(`new_interior = 1 + 1 + S`, `old_interior = e − b − 1`).

The reported rows use exactly these expressions (see `build_rows`), so by I1
each row is correct for the rewritten file. For the INDEX_BLOCK row:
start = `b + 1` (the BEGIN marker never moves), end = `b + new_interior + 2`
(1-indexed END position). ∎

**Idempotence:** after the rewrite, stored interior size = `new_interior`,
so a second computation yields `delta' = 0` and recomputes identical rows for
the same sections (their relative order and count are unchanged).
`check` compares stored vs computed interiors, so it passes. ∎

**Section spans:** a section runs from its marker to the line before the next
section's marker (or the last line of the file). Reported end =
`next_start − 1 + delta`, which by I1 is the correct final line. ∎

### 2.4 Complexity

One linear scan for the block (O(L)), one linear scan for sections (O(L)),
row construction O(S), rewrite O(L) (list splice + join). **Total O(L),
space O(L)** for `sync`, O(S) for the row model. Observed complexity matches
the ideal; no hidden quadratic term.

### 2.5 Deviations

Backfilled against `ad0fc9f`; observed gaps between ideal and actual:

1. **Triplication.** The core exists in three independent copies
   (`backlog_index.py`, `algorithm_index.py`, `manage_lessons.py`) with
   different row formats. Deliberate vendoring decision (LLT-0002) to keep
   hooks/CI self-contained; consolidation into the `securetrace` package is
   backlog B3 (this change set).
2. **`fail()` exits the process** from inside parse functions
   (`sys.exit(2)`), i.e. error handling is a side effect rather than a
   returned/raised value. Tests must therefore run the scripts as
   subprocesses. B3 moves this to an exception hierarchy.
3. **A second index block is body text — not an error, and not inert.**
   `find_index_block` stops at the first END marker; a second BEGIN/END pair
   later in the file becomes part of the last section's span, which changes
   that section's reported end line — so `--check` reports stale (exit 1)
   until the next `sync`. `sync` rewrites only the first block's interior;
   the second pair survives as body text (verified — test P13).
4. **Two-tier heading parse (backlog only).** A heading without a
   `— **STATUS**` suffix still matches the loose fallback and yields status
   `-` in the row rather than an error: a statusless item heading is
   *accepted*, not rejected.
5. **Line-ending normalization.** `splitlines()` + `"\n".join` means `sync`
   rewrites CRLF files with LF endings (verified — proposed test P8).
6. **Placeholder dash differs by format:** backlog/algorithm rows use `-`,
   the lessons variant uses `—` (em dash). Mixing them breaks `check`.
7. **Priority parsing does not see bulleted lines.** `PRIORITY_RE` is
   `^\s*\*\*Priority:\*\*\s*(\S+)\s*$` (case-insensitive): it matches only a
   line that *starts* with `**Priority:**` (after optional whitespace). The
   bulleted form `- **Priority:** High` — used by this repo's BACKLOG.md and
   by the skill's own `references/item-anatomy.md` — never matches, so the
   row priority silently falls back to `Low`, and an out-of-vocabulary value
   on a bulleted line is **not rejected**. Only the unbulleted form (the
   skill's `references/example-backlog.md`) is parsed and vocabulary-checked
   (verified — tests P9a/P9b/P9c). The vendored script is logic-identical to
   the skill original (diffed; line-wrapping differences only), so this is
   the skill's own behavior. B3 preserves it as pinned (recorded as
   LLT-0009; a fix would be a separate doc-first change).
8. **The scan window excludes the last line of a section.** `build_rows`
   calls `parse_item_heading`/`parse_priority` with `(start - 1, stop - 1)`,
   so the 0-indexed window `lines[start - 1 : stop - 1]` never examines the
   section's *last* line (for the final section, the file's last line). An
   unbulleted `**Priority:** X` on that line is silently indexed as `Low`
   — even an out-of-vocabulary value is **not rejected** (exit 0) — and an
   item heading on that line is not parsed. The quirk is latent in typical
   files (sections normally end with a blank line before the next marker)
   and only bites when the line of interest is the file's last line
   (verified — `test_priority_on_final_line_not_scanned_quirk`; LLT-0012).
   B3 preserves it as pinned; a fix (include the last line in the window)
   is a separate doc-first change.

<!-- SECTION:PSEUDOCODE -->
## 3. Pseudocode

Faithful to `scripts/backlog_index.py` at `ad0fc9f` (algorithm variant is
identical except `find_sections` has no item/reserved-id checks and rows carry
no title/status/priority). Quirks are flagged `# DEV:` and map to §2.5.

```
find_index_block(lines) -> (b, e)
    b := -1; e := -1
    for i := 0 .. |lines| - 1:
        if b == -1 and BEGIN_RE matches lines[i]: b := i        # first BEGIN wins
        else if b != -1 and END_RE matches lines[i]: e := i; break   # first END after it
    if b == -1 or e == -1: error "missing INDEX:BEGIN / INDEX:END markers"
    if e <= b + 1: error "index block is empty or malformed"    # interior must exist
    return (b, e)

find_sections(lines, e) -> S
    S := []; seen := {}
    for i := 0 .. |lines| - 1:
        if not a marker: continue   # KIND/ITEM marker regexes; unknown kinds ignored
        if i <= e:
            error "marker at line i+1 is at or inside the index block"  # invariant: sections after END
        id := item id or section kind; is_item := id is an ITEM marker
        if is_item and id in {HEADER, QUEUE, CONSTRAINTS}:
            error "item id is reserved for a section name"
        if id in seen: error "duplicate section marker: id"             # uniqueness guard
        seen.add(id); S.append((id, i + 1, is_item))                    # 1-indexed start
    if no entry of S has is_item: error "no ITEM markers found"
    return S

build_rows(S, L, b, e) -> rows
    old := e - b - 1                  # stored interior size
    rows := 1 + |S|                   # INDEX_BLOCK + one per section
    new := 1 + rows                   # TSV header + rows
    d := new - old                    # the single constant shift (I1)
    out := [(INDEX_BLOCK, "-", "-", "-", b + 1, b + new + 2)]  # self-row, post-rewrite coords
    for k := 0 .. |S| - 1:
        stop := S[k+1].start - 1  if k + 1 < |S|  else  L       # 1-indexed inclusive
        if S[k].is_item:
            # Pinned call is (start-1, stop-1): window lines[start-1 : stop-1]
            # EXCLUDES the section's last line (the file's last line for the
            # final section) — heading/priority there are never parsed (DEV(8)).
            (title, status) := parse_item_heading(S[k].id, lines, S[k].start - 1, stop - 1)
            priority := parse_priority(S[k].id, lines, S[k].start - 1, stop - 1)
            # parse_item_heading: first line matching strict
            #   ## <ID>. <title> [—–-] **OPEN|IN PROGRESS|DONE|CANCELLED** (case-insensitive)
            #   -> (title, STATUS with spaces -> underscores)
            # else first line matching loose  ## <ID>. <title>
            #   -> (title, "")            # DEV(4): statusless heading is accepted, renders "-"
            # parse_priority: first line matching ^\s*\*\*Priority:\*\* -> High/Medium/Low
            #   case-insensitive; absent -> Low (G9); out-of-vocab -> error "not one of High, Medium, Low"
            #   DEV(7): bulleted `- **Priority:** X` lines NEVER match -> default Low;
            #   the out-of-vocab error can only fire on an unbulleted line
        else: (title, status, priority) := ("-", "-", "-")
        out.append((S[k].id, title, status, priority, S[k].start + d, stop + d))
    return out

render(rows) -> C
    C := [TSV_HEADER]
    for r in rows: C.append(tab-join(sanitize(cells of r)))   # sanitize: tabs -> space, strip, "" -> "-"
    return C

sync(text) -> text'
    lines := splitlines(text); (b, e) := find_index_block(lines)
    S := find_sections(lines, e)
    C := render(build_rows(S, len(lines), b, e))
    return join(lines[0..b] ++ C ++ lines[e..])               # only the interior moves
    # DEV(5): join with "\n" normalizes CRLF input to LF

check(text) -> ok | STALE
    (b, e, S, C) := same computation as sync
    if lines[b+1 .. e) == C: ok
    else: STALE                                                # exit 1
```

<!-- SECTION:WALKTHROUGH -->
## 4. Walk-through (plain English)

### 4.1 Step-by-step

1. Scan the lines once, left to right, to find the index block: the first line
   matching the BEGIN pattern and the first END pattern after it. If either is
   missing, or if there is no interior between them, the file is malformed
   (exit 2).
2. Scan again for section markers. Every marker must sit *after* the block's
   END line; each marker id must be unique; an item may not use a reserved
   section name; at least one item must exist. Record each section's 1-indexed
   start line.
3. Compute the geometry: how many interior lines are stored now (`old`), how
   many the new table needs (`new` = header + 1 + number of sections), and the
   single shift `d = new − old`.
4. Emit the rows in the *final* file's coordinates: the INDEX_BLOCK row
   (start = BEGIN line, end = BEGIN line + new interior + 1), then one row per
   section with every line number shifted by `d`. For backlog items, also pull
   the title/status from the first `## <ID>. …` heading and the priority from
   the first line that *starts* with `**Priority:**` — a bulleted
   `- **Priority:** …` line never matches and silently yields `Low` (DEV(7)).
5. `sync`: splice the new interior between the two markers and write.
   `check`: compare stored interior to the computed one; equal means fresh.
   Because step 4 already accounts for the block's final size, running `sync`
   twice is a no-op on the second run.

### 4.2 Worked example

Sample input: `BACKLOG_FIXTURE` from `tests/scripts/test_skill_scripts.py`
(27 lines; markers at lines 3–5; sections HEADER@7, QUEUE@12, B1@17,
CONSTRAINTS@24; B1 has `## B1. Bootstrap — **OPEN**` and a bulleted
`- **Priority:** High`).

- `b = 2`, `e = 4` (0-indexed), `L = 27`.
- `old = 4 − 2 − 1 = 1` (the one placeholder line).
- 4 sections → `rows = 5`, `new = 6`, **`d = 6 − 1 = 5`**.
- Rows (1-indexed, final-file coordinates):
  - `INDEX_BLOCK  -  -  -  3  10` (end = `b + new + 2 = 2 + 6 + 2`)
  - `HEADER  -  -  -  12  16` (start `7+5`; stop `12−1+5`)
  - `QUEUE  -  -  -  17  21`
  - `B1  Bootstrap  OPEN  Low  22  28` (title/status parsed; priority `Low`
    — the bulleted priority line does not match `PRIORITY_RE`; DEV(7))
  - `CONSTRAINTS  -  -  -  29  32` (stop = `L + d = 27 + 5`)
- Rewritten file has `27 + 5 = 32` lines; its END marker is on line 10.
- Re-run on the rewritten file: `old = 6 = new` → `d = 0` → identical rows →
  `check` passes. Idempotent, exactly as §2.3 predicts.

<!-- SECTION:IMPLEMENTATION -->
## 5. Implementation notes (entry-level guide)

### 5.1 Data structures

- **Section:** triple `(row_id: str, start: int, is_item: bool)` — `start` is
  1-indexed in the *input* file. Invariant: starts strictly increasing;
  all `> e`.
- **Row:** 6-tuple `(id, title, status, priority, start, end)` (backlog);
  3-tuple for the algorithm variant. Sentinels: `-` (hyphen) for absent
  title/status/priority — chosen because the TSV is the machine contract and a
  single-character placeholder cannot be confused with a real value. The
  lessons variant uses `—` (em dash) instead; see DEV(6).
- **`seen` set:** marker ids already accepted; O(1) duplicate detection.
- Cost notes: all structures are O(S); the dominant allocation is the
  rewritten line list, O(L).

### 5.2 Edge cases and defined behavior

| Case | Defined behavior | Why |
|---|---|---|
| No BEGIN/END markers | error, exit 2 | no block, no index to maintain |
| BEGIN immediately followed by END (empty interior) | error, exit 2 | interior must hold at least the TSV header |
| Section marker on/inside the block (`i <= e`) | error, exit 2 | geometry invariant (all sections after END) |
| Duplicate marker id | error, exit 2 | row id must be unique (registry guard G3/G5) |
| Item id = `HEADER`/`QUEUE`/`CONSTRAINTS` | error, exit 2 (backlog) | reserved section names |
| Zero sections / zero items | error, exit 2 | a record with no content is malformed |
| No line starting with `**Priority:**` | row priority `Low` | G9 default |
| Bulleted `- **Priority:** X` line (any X) | **no match** — row priority `Low`, accepted, no error | `PRIORITY_RE` cannot see a leading bullet — DEV(7) |
| Unbulleted `**Priority:** X` with X a single out-of-vocabulary token | error, exit 2 | vocabulary guard (unbulleted form only — DEV(7)) |
| Item heading present without status | row status `-` (accepted) | loose fallback regex — DEV(4) |
| Tab inside a title cell | replaced with a space in the row | TSV cells must not contain tabs |
| File without trailing newline | preserved (no newline added) | `had_trailing_newline` flag |
| CRLF line endings | `sync` normalizes to LF | `splitlines` + `"\n".join` — DEV(5) |
| Second BEGIN/END pair later in file | body text: last row's end line changes → `--check` stale (exit 1) until sync; `sync` rewrites first block only, pair survives | `find_index_block` stops at first END — DEV(3) |

### 5.3 Invariants and how to test them

1. **All section markers after the block.** Test: place a marker before the
   BEGIN line → expect exit 2.
2. **Marker ids unique.** Test: duplicate `<!-- BACKLOG:QUEUE -->` → exit 2.
3. **Single-delta geometry** (rows correct for the final file). Test: sync,
   then assert the last section's reported end equals the file's line count.
4. **Idempotence** `sync(sync(t)) == sync(t)`. Test: double-sync, compare
   bytes; then `--check` passes (proposed P7).
5. **Staleness detected.** Test: append one line to a section body → `--check`
   exit 1 (existing roundtrip test).

### 5.4 Pitfalls and known traps

- **Off-by-one in the self-row:** END line is `b + new_interior + 1`
  0-indexed = `b + new_interior + 2` 1-indexed; the `+2` is the classic trap.
- **Delta sign:** `delta` is positive when the block grows and negative when
  it shrinks (removing a section). The formulas work for both; do not assume
  positive.
- **`fail()` is `sys.exit`, not an exception** (DEV(2)) — in-process tests
  catch `SystemExit`; the real test suite uses subprocesses.
- **Placeholder dash mismatch** (`-` vs `—`) silently breaks `check` across
  the two formats (DEV(6)).
- **Priority only from unbulleted lines:** `- **Priority:** High` (the form
  BACKLOG.md and the skill's `item-anatomy.md` reference use) renders as
  `Low` in the row, and an out-of-vocabulary bulleted value is never rejected
  (DEV(7), LLT-0009).
- **Scan window excludes the section's last line** (DEV(8), LLT-0012):
  `build_rows` passes `stop − 1` as the exclusive stop, so a heading or
  priority line sitting on the last line of a section — the file's last line
  for the final section — is never parsed; an out-of-vocabulary value there
  is not rejected.
- **`re.IGNORECASE` scope:** applied to priority and status keywords only;
  marker ids remain case-sensitive (`[A-Z]`).
- **Trailing `\s*$` in marker regexes** tolerates trailing spaces — but a tab
  *inside* a title is only sanitized at render time, not at parse time.

### 5.5 Language notes

- Python 3: `re` module, patterns compiled once at module level (no per-call
  recompilation). `str.splitlines()` is the line splitter (it also accepts
  `\r\n`, which is how DEV(5) arises).
- The splice idiom `lines[:b+1] + block + lines[e:]` keeps the BEGIN marker
  (index `b`) and the END marker (index `e`) in place.
- Type annotations: `list[str]`, `tuple[int, int]`, `tuple[str, int, bool]` —
  the B3 package port promotes these tuples to dataclasses (`Section`, `Row`)
  without changing any formula.

<!-- SECTION:TESTS -->
## 6. Test cases and sample data

All sample data is synthetic (the fixtures below are lifted from
`tests/scripts/test_skill_scripts.py`, which exercises the pinned
implementation via subprocess).

| # | Name | Input (sample data) | Expected output | Why it matters |
|---|---|---|---|---|
| 1 | roundtrip: sync then check (existing, `test_backlog_index_roundtrip`) | 27-line fixture: block at lines 3–5; HEADER/QUEUE/`ITEM:B1`/CONSTRAINTS sections; B1 heading `## B1. Bootstrap — **OPEN**`, `- **Priority:** High` (bulleted) | `sync` exit 0, prints `index updated (5 entries)`; `--check` exit 0, prints `index OK (5 entries)`; rows as traced in §4.2 (B1 priority `Low` per DEV(7); the test asserts exit codes only) | happy path; pins row geometry and idempotence |
| 2 | staleness after body edit (existing, same test) | case-1 fixture + one appended line inside B1 | `--check` exit 1, stderr `index STALE -- rerun without --check`; `sync` then `--check` exit 0 again | the gate must actually detect drift |
| 3 | missing markers (existing, `test_backlog_index_rejects_missing_markers`) | `# Backlog\n\nno markers at all\n` | exit 2, stderr `missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers` | error model: no block |
| 4 | roundtrip: algorithm variant (existing, `test_algorithm_index_roundtrip`) | block + `SECTION:METADATA`/`THEORY`/`TESTS` | `sync` 0; `--check` 0; after appending a theory line, `--check` 1; resync 0 | second format of the same core |
| 5 | single item (proposed, verified) | minimal fixture: block + one `ITEM:B1` with heading `## B1. Work — **OPEN**` + bulleted `- **Priority:** High` | `sync` 0; `--check` 0; exactly 2 rows; the B1 row reads `B1\tWork\tOPEN\tLow\t…` (priority `Low` per DEV(7)) | minimal valid input (G5); row content asserted, not just the exit code |
| 6 | duplicate marker (proposed, verified) | two `<!-- BACKLOG:QUEUE -->` lines | exit 2, stderr `duplicate section marker: QUEUE` | uniqueness guard |
| 7 | reserved item id (proposed, verified) | `<!-- BACKLOG:ITEM:HEADER -->` | exit 2, stderr `item id HEADER is reserved for a section name` | reserved-id guard |
| 8 | marker inside block (proposed, verified) | `<!-- BACKLOG:HEADER -->` on line 4 (between BEGIN and END) | exit 2, stderr `marker at line 4 is at or inside the index block` | geometry invariant |
| 9a | bulleted priority out of vocabulary (existing, `test_bulleted_priority_is_ignored_quirk`) | `- **Priority:** Urgent` (bulleted) | **accepted**: row priority `Low`, no error | DEV(7) — the vocabulary guard never sees bulleted lines (LLT-0009) |
| 9b | unbulleted priority out of vocabulary (existing, `test_unbulleted_priority_out_of_vocabulary_rejected`) | `**Priority:** Urgent` + a trailing body line (the priority line is NOT the file's last line — DEV(8)) | `FormatError`: `priority 'Urgent' is not one of High, Medium, Low (G9)` | vocabulary guard (unbulleted form only — DEV(7)) |
| 9c | unbulleted priority in vocabulary (existing, `test_unbulleted_priority_in_vocabulary_parsed`) | `**Priority:** High` + a trailing body line (NOT the file's last line — DEV(8)) | B1 row priority `High` | the only form `PRIORITY_RE` parses |
| 9d | unbulleted priority on the file's last line (existing, `test_priority_on_final_line_not_scanned_quirk`) | `**Priority:** Urgent` as the file's last line | **accepted**: B1 row priority `Low`, no error | DEV(8) — the scan window excludes the section's last line (LLT-0012) |
| 10 | status normalization (proposed, verified) | heading `## B1. Work — **IN PROGRESS**` | row status `IN_PROGRESS` | `IN PROGRESS` → `IN_PROGRESS` mapping |
| 11 | idempotence (proposed, verified) | case-1 fixture, `sync` twice | second `sync` output byte-identical; `--check` 0 | §2.3 idempotence proof |
| 12 | CRLF handling (proposed, verified) | case-1 fixture with CRLF endings | read via universal newlines (CRLF→LF); any actual write emits LF; a fresh `--check` performs no write, so an on-disk CRLF file stays untouched | DEV(5); the mechanism is text-mode `open().read()`, not `splitlines` alone (LLT-0011) |
| 13 | second index pair (proposed, verified) | fresh file (synced, `--check` 0), then a second BEGIN/END pair appended after the last section | `--check` exit 1 (stale — last row's end line changed); `sync` 0; `--check` 0 again; the second pair survives as body text | DEV(3) — not an error, and not inert |

### 6.1 Property tests (optional but preferred)

- **Idempotence:** for any well-formed `t`, `sync(sync(t)) == sync(t)`.
- **Staleness sensitivity:** for any well-formed `t` and any line edit outside
  the block interior, `check(t')` is stale unless the edit leaves all reported
  ranges and item metadata unchanged.
- **Row geometry:** for the last row, `end_line == line_count(sync(t))`.

### 6.2 Performance acceptance

O(L) claim is not load-bearing at current sizes (records are a few hundred
lines); no budget set. A 100k-line file should sync in well under a second on
a laptop-class machine (claimed, unverified).

<!-- SECTION:REFERENCES -->
## 7. References

- `scripts/backlog_index.py`, `scripts/algorithm_index.py`, `scripts/manage_lessons.py` at `mirph-glitch42/SecureTrace@ad0fc9f` (pinned implementations).
- `tests/scripts/test_skill_scripts.py` — contract tests pinning exit codes and roundtrip behavior.
- Skill `backlog-manager` (guards G3/G5/G9), `algorithm-records-keeper` (guards G5/G8 — template, ex-post-facto workflow), `learned-lesson-tracker` (index format).
- `algorithms/lessons-record.md` — the third format that reuses the delta core.
- `LESSONS_LEARNED.md` LLT-0002 (vendoring decision behind the triplication, DEV(1)).
- `LESSONS_LEARNED.md` LLT-0009 (priority-regex mismatch, DEV(7)), LLT-0011 (universal-newline reads, DEV(5)), and LLT-0012 (last-line scan-window exclusion, DEV(8)).
- `tests/backlog/test_index.py` (B3) — behavioral tests of the pure core, including the DEV(7)/DEV(8) quirk pins.
