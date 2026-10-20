# Lessons Record (append-only entry log with a derived self-describing TSV index)

<!-- INDEX:BEGIN format=tsv version=1 -->
id	start_line	end_line
INDEX_BLOCK	3	13
METADATA	15	37
THEORY	38	210
PSEUDOCODE	211	384
WALKTHROUGH	385	467
IMPLEMENTATION	468	595
TESTS	596	657
REFERENCES	658	666
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Lessons Record (append-only entry log with a derived self-describing TSV index) |
| Slug | lessons-record |
| Version | 0.1.2 |
| Status | backfilled |
| Author | SecureTrace bootstrap (mirph-glitch42) |
| Created | 2026-10-18 |
| Last modified | 2026-10-19 |
| Status history | 0.1.0 (2026-10-18): backfilled from `ad0fc9f`<br>0.1.1 (2026-10-19): cited digit classes synced to the ASCII-scoped form (`(?a:\d)`) — behavior-identical (B7 increment 1)<br>0.1.2 (2026-10-19): cited `HEADING_RE`/`FIELD_RE` value patterns synced to the linear-time form (`\S+(?:\s+\S+)*` / `\S*(?:\s+\S+)*`) — behavior-identical (B7 increment 4) |
| Pinned to | `mirph-glitch42/SecureTrace@ad0fc9f` (2026-10-18) |
| Languages | Python 3 (reference implementation); algorithm is language-agnostic |
| Implementation location | <br>`scripts/manage_lessons.py:L79-L134` (constants, vocabularies, exceptions, `Entry`) — `L158` (`atomic_write`) — `L173-L313` (`find_index_block`, `parse_entries`, `check_consistency`, `structural_errors`) — `L334-L390` (delta core: `expected_index_rows`, `index_is_fresh`, `regenerate`) — `L409-L467` (`build_template`, `render_entry`, `max_id`, `cmd_init`, `validate_add_args`) — `L492-L605` (`cmd_add`, `cmd_sync`, `cmd_check`, `cmd_next_id`) — `L607-L674` (`build_parser`, `main`) |
| Time complexity | O(L) per operation (L = physical line count); supersession cross-check O(E²), E = entry count — observed, matches ideal |
| Space complexity | O(L) for `add`/`sync` (new line list); O(E) for the entry model |
| Determinism | deterministic, except `add` defaults `Recorded` to the host's current date when `--recorded` is omitted |
| Dependencies | none (Python stdlib: `re`, `argparse`, `tempfile`, `os`, `datetime`, `dataclasses`) |
| Thread safety | pure text core is thread-safe (no shared state); file I/O is caller-serialized; writes are atomic (`os.replace`) |
| Related documents | <br>`algorithms/line-index-sync.md` (shared delta core — cross-referenced, not re-derived)<br>`LESSONS_LEARNED.md` (the live record managed by this algorithm)<br>`LESSONS_LEARNED.md` LLT-0002 (vendoring decision behind the triplication) |

<!-- SECTION:THEORY -->
## 2. Theory

### 2.1 Problem definition

A project's lessons-learned record is an **append-only log** of atomic lessons
(one situation, one pitfall, one correct solution each), written by agents as
they are learned, and read back by agents that must not relearn the same
mistake. The record must be navigable without loading the whole file: it
carries a **self-describing index block** — a TSV table delimited by
`<!-- LLT:INDEX:BEGIN -->` / `<!-- LLT:INDEX:END -->` markers that lists every
entry's id, title, category, severity, status, recorded date, and line range.
The first data row always describes the block itself, so the index is
inclusive of itself (the delta core documented in `line-index-sync.md`).

The contract (reference implementation, `manage_lessons.py` at `ad0fc9f`):

- **Entry anatomy (G6):** each entry is a marker
  `<!-- LLT:ENTRY:LLT-NNNN -->`, an em-dash heading
  `## LLT-NNNN — <title>` (marker id == heading id, G8), and ten
  `- **Field:** value` lines: seven required
  (`Recorded` `YYYY-MM-DD`, `Category`, `Severity`, `Status`, `Context`,
  `Pitfall`, `Solution`) and three optional (`Supersedes`, `Prevention`,
  `References`) that read `—` when absent. `Category`/`Severity`/`Status`
  draw from fixed closed vocabularies. Values are single-line, tab-free.
- **Stable ids (G4):** ids match `LLT-[0-9]{4}`, are assigned once, never
  reused or renumbered, and strictly increase in file order. Entries are
  appended only — never moved, edited in place (except `Status` flips done by
  supersession), or deleted.
- **Supersession (G7) is a bidirectional data invariant:** an entry whose
  `Supersedes` is an id must point at an entry whose `Status` is
  `superseded`; conversely every `superseded` entry must be pointed at by at
  least one `Supersedes` field. The file may change its mind without losing
  history.
- **Derived index (G5):** the index block is *derived state*. `sync` (and
  `add`) regenerate it from the entries; `check` compares the stored block
  with the derived one. Never edit the block by hand.
- **Exit model (all subcommands):** `0` ok; `1` index stale (fix with
  `sync`); `2` malformed file or rejected input (structure, fields,
  vocabulary, ids, supersession, or refusal to overwrite).
- **Safety:** `add` never writes a file it cannot then validate; a valid
  existing record is never overwritten by `init`, even with `--force`.

### 2.2 Why this approach

**Chosen: derived index + single-delta rewrite (shared core).** The block's
size depends on the entry count and its insertion shifts every entry below,
so line numbers are computed in *post-rewrite* coordinates with one constant
delta (`new_end = begin + 3 + E`, `delta = new_end − end`). This is the same
core as `line-index-sync.md` (third format); see that document for the
rejected alternatives (iterative fixed point, pre-rewrite numbers, byte
offsets) — all rejected for the same reasons here.

**Chosen: append-only + supersession instead of in-place editing.** Lessons
are citations (commit messages, other skills' `References`, postmortems all
point at `LLT-NNNN`). Reuse or renumbering would silently redirect every
existing citation. Supersession flips exactly one `Status` line in the target
entry's span and appends the replacement — history stays, truth stays current.

**Rejected: prose-only log + `grep`.** Works for humans, but the index is how
*agents* navigate without loading the whole file, and staleness is exactly
the failure mode that is silent to a skimmer and catastrophic to a machine
(guard G5). A grep-able fixed field set (guard G6) is the machine half of the
same contract.

**Rejected: one shared script for all three record formats (backlog /
algorithm / lessons).** The formats' row schemas and vocabularies differ; a
unified parser would carry format-conditional branches everywhere. The
deliberate alternative was vendoring one small self-contained script per
format (LLT-0002) so hooks/CI run without the skill directory; consolidation
into the `securetrace` package is backlog B3.

### 2.3 Correctness argument

**I1 (block first, unique).** `find_index_block` accepts the first BEGIN and
the first END after it; `structural_errors` raises `FileError` if the block
is missing/empty or if any entry marker precedes it. Hence all entries lie
strictly after `end` — the precondition for the single-delta rewrite.

**I2 (entry well-formedness).** `parse_entries` enforces per-entry marker/
heading agreement, the closed field set, required/non-empty fields,
vocabularies, and tab-free single-line values. Errors are *collected*, not
fail-fast, so a single `check` reports every defect (verified — L14/L15 files
report each named violation).

**I3 (supersession bidirectionality).** `check_consistency` verifies both
directions of the invariant (target exists and is `superseded`; successor
exists), so a half-flipped state — the one that would corrupt the record's
truth — is unrepresentable in a passing file.

**I4 (append order).** Ids strictly increase; `add` enforces
`--id > max` (or assigns `max + 1`), so the file order is the order learned.

**I5 (derived index).** `expected_index_rows` is a pure function of the
entries; `index_is_fresh` is the equality of stored vs derived interior;
`regenerate` is the splice that makes the stored equal the derived.
Idempotence: after `regenerate`, stored interior size == required size, so
`delta' = 0` and a second run is byte-identical (verified — L18).

**`add` safety.** Pipeline order (verified by full read + L13a): structural
check → `Recorded` default → input validation → supersession flip (inside the
target span only) → id assignment → append entry → `regenerate` →
**re-validate the generated text** (`structural_errors` must be empty and
`index_is_fresh` true) → `atomic_write`. A `FileError`/`InputError` raised at
any point means no write happened; the two internal-error guards mean even a
hypothetical generation bug cannot persist a malformed file. `atomic_write`
(NamedTemporaryFile in the target directory + `os.replace`) means a crash mid-
write cannot truncate the record. ∎

**Supersession flip locality.** The flip rewrites the first `- **Status:**`
line in `lines[target.start − 1 .. target.end)`. By I1 that range contains
only the target entry (marker, heading, fields) — no other entry's `Status`
line can be touched, and `L13a` confirms exactly one `superseded` line
results. ∎

### 2.4 Complexity

One linear scan per operation: block O(L), entries O(L) (each line visited in
at most one entry span), supersession cross-check O(E²) (successor scan per
superseded entry; first id-order violation reported, then stopped), row
construction O(E), splice O(L). **Total O(L) for `check`/`sync`/`next-id`,
O(L) + O(E²) for the consistency part of `check`/`add`**, space O(L). The
O(E²) term is not load-bearing at record scale (tens of entries; even 10k
entries is 10⁸ simple comparisons, still sub-second in CPython — claimed,
unverified).

### 2.5 Deviations

Backfilled against `ad0fc9f`; observed gaps between ideal and actual
(all verified this session against the pinned script):

1. **Triplication.** The delta core exists in three independent copies with
   different row formats. Deliberate vendoring decision (LLT-0002);
   consolidation is backlog B3. See `line-index-sync.md` DEV(1).
2. **Mixed error surface.** `main()` *returns* the exit code (it does not
   `sys.exit`; `__main__` does `sys.exit(main())`) and maps
   `FileError`/`InputError` → 2, `StaleIndex` → 1. But individual commands
   split the same class of failure two ways: structural problems in an
   existing file are printed one-per-line to stderr and returned as `2`
   (e.g. L14/L15), while input problems *raise* `InputError` and print a
   single prefixed `manage_lessons: …` line. Both exit 2; the stderr shape
   differs. The B3 package port unifies this (exceptions + one command layer).
3. **`Recorded` is format-only, not calendar-checked.** `DATE_RE` is
   `^[0-9]{4}-[0-9]{2}-[0-9]{2}$`: `2026-99-99` is **accepted** (verified —
   L7a) and `2026-1-1` rejected (L7b). No month/day range validation.
4. **Staleness covers geometry + indexed fields, not body content.** The
   index records line ranges plus six fields (title/category/severity/
   status/recorded). A same-line body edit (e.g. rewriting `Context`) is
   **not** stale — `check` exits 0 (verified — L19d). A line-count change
   (L19a) or an indexed-field change (L19c) **is** stale (exit 1). Structural
   and field validation still runs on every `check`; a malformed file is
   exit 2 regardless of staleness.
5. **CRLF behavior is a read-time phenomenon.** `Path.read_text()` (text
   mode) applies universal newlines, so CRLF becomes LF *at read time*;
   `split("\n")` then sees a clean line list. A fresh `check`/`sync`
   performs no write, so an on-disk CRLF file survives byte-identical
   (verified — L20a/L20b). Any actual write (`add`, stale `sync`) emits LF.
   See `line-index-sync.md` DEV(5) and LLT-0011.
6. **Placeholder dash is the em dash `—`** in every lessons row cell
   (title/category/… and the self-row), versus `-` in the backlog/algorithm
   formats; mixing them breaks `check`. See `line-index-sync.md` DEV(6).
7. **The last entry's `end_line` overshoots the file's last line by one.**
   `text.split("\n")` leaves a phantom empty element when the text ends with
   a newline, so for the final entry `e.end = len(lines)` = (actual last line)
   + 1, and the row reports `e.end + delta` = actual last line + 1.
   Verified: the single-entry 29-line file reports row end `30`; the
   two-entry 44-line file reports `45` for LLT-0002. Interior entries report
   the line *before* the next marker (span-inclusive, which includes the
   separating blank line: LLT-0001 reports end `31` where line 31 is the
   blank before marker 2). The skill's `entry-anatomy.md` spec says
   "last line of the entry (inclusive)" — the implementation overshoots by
   one for the final entry only.

<!-- SECTION:PSEUDOCODE -->
## 3. Pseudocode

Faithful to `scripts/manage_lessons.py` at `ad0fc9f`. Quirks are flagged
`# DEV:` and map to §2.5. The delta core (`expected_index_rows`,
`index_is_fresh`, `regenerate`) is the shared algorithm documented in
`line-index-sync.md` §3; only the lessons-specific row schema and the
`begin + 3 + E` end formula are shown here.

```
constants
    REQUIRED  := (Recorded, Category, Severity, Status, Context, Pitfall, Solution)
    OPTIONAL  := (Supersedes, Prevention, References)
    CATEGORIES := (debugging, architecture, testing, performance, security,
                   dependencies, tooling, environment, process, data, other)
    SEVERITIES := (low, medium, high, critical)
    STATUSES   := (active, superseded)
    ID_RE   := ^LLT-(?a:\d){4}$
    DATE_RE := ^(?a:\d){4}-(?a:\d){2}-(?a:\d){2}$    # DEV(3): format-only, no calendar validation
    HEADER  := "id\ttitle\tcategory\tseverity\tstatus\trecorded\tstart_line\tend_line"

find_index_block(lines) -> (begin | none, end | none)
    # DEV(2): this function never errors; it reports absence
    for i := 0 .. |lines| - 1:
        if begin == none and BEGIN_RE matches lines[i]: begin := i
        else if begin != none and END_RE matches lines[i]: end := i; break
    return (begin, end)

parse_entries(lines) -> (entries, errors)
    for i, line in lines:
        if ENTRY_MARKER_RE does not match line: continue        # <!-- LLT:ENTRY:LLT-NNNN -->
        eid := marker id
        if eid in seen: errors += "duplicate entry marker {eid} (line {i+1}); ids must be unique (G4)"
        seen.add(eid)
        j := i + 1
        while j < |lines| and lines[j] is not an ENTRY_MARKER: j += 1
        # DEV(7): j == |lines| includes the phantom "" element when text ends with a newline
        heading := first line in lines[i+1 .. j) matching  ## LLT-NNNN — <title>   # em dash required
        if heading is none:
            errors += "entry {eid}: missing heading '## {eid} — <title>' in lines {i+1}-{j} (G8)"
        else:
            if heading.id != eid:
                errors += "entry marker {eid} (line {i+1}) disagrees with heading id {heading.id} (line {heading.line}); marker and heading must match (G8)"
            if heading.title contains a tab: errors += "entry {eid}: title contains a tab character (G6)"
        fields := {}
        for k := i + 1 .. j - 1:
            if FIELD_RE (- **Name:** value) does not match lines[k]: continue
            name := field name
            if name not in REQUIRED + OPTIONAL:
                errors += "entry {eid}: unknown field '{name}' (line {k+1}); allowed: ..."; continue
            if name in fields: errors += "entry {eid}: duplicate field '{name}' (line {k+1})"; continue
            if value contains a tab: errors += "entry {eid}: field '{name}' contains a tab character (G6)"
            fields[name] := value
        for req in REQUIRED:
            if req not in fields: errors += "entry {eid}: missing required field '{req}' (G6)"
            elif fields[req] is empty: errors += "entry {eid}: required field '{req}' is empty (G6)"
        if fields[Recorded] present and does not match DATE_RE:
            errors += "entry {eid}: Recorded '{v}' is not YYYY-MM-DD (G6)"
        for (name, vocab) in [(Category, CATEGORIES), (Severity, SEVERITIES), (Status, STATUSES)]:
            if fields[name] present and not in vocab:
                errors += "entry {eid}: {name} '{v}' not in vocabulary: ... (G6)"
        if fields[Supersedes] present and != "—" and does not match ID_RE:
            errors += "entry {eid}: Supersedes '{v}' must be an LLT-NNNN id or — (G7)"
        for opt in (Prevention, References):
            if opt in fields and fields[opt] is empty:
                errors += "entry {eid}: optional field '{opt}' is empty; write — when absent (G6)"
        entries.append(Entry(id=eid, title=heading.title, fields, start=i+1, end=j))
    return (entries, errors)      # errors collected, not fail-fast

check_consistency(entries) -> errors
    # DEV: O(E^2) supersession scan — fine at record scale (§2.4)
    for e in entries:
        sup := e.fields[Supersedes] or "—"
        if sup == "—": continue
        if sup not in entries: errors += "entry {e.id}: Supersedes {sup}, which does not exist (G7)"
        elif entries[sup].fields[Status] != "superseded":
            errors += "entry {e.id}: Supersedes {sup}, but {sup} is not marked superseded (G7)"
    for e in entries with Status == "superseded":
        if no other entry has Supersedes == e.id:
            errors += "entry {e.id} is superseded but no entry supersedes it; add the replacement with --supersedes {e.id} (G7)"
    for (a, b) in adjacent numeric id suffixes, in file order:
        if b <= a:
            errors += "entry ids must strictly increase in file order (append-only); found {a} followed by {b} (G4)"
            break                              # first violation only
    return errors

structural_errors(text) -> errors            # raises FileError for a broken skeleton
    lines := text.split("\n")
    (begin, end) := find_index_block(lines)
    if begin == none or end == none: RAISE FileError "missing <!-- LLT:INDEX:BEGIN --> / <!-- LLT:INDEX:END --> markers (G8)"
    if end <= begin + 1: RAISE FileError "index block is empty or malformed (G8)"
    for i, line in lines:
        if ENTRY_MARKER_RE matches line and i < begin:
            RAISE FileError "entry marker at line {i+1} appears before the index block; the index must be first (G8)"
    entries, errors := parse_entries(lines)
    return errors + check_consistency(entries)

expected_index_rows(text) -> rows            # shared core — see line-index-sync §3
    (begin, end) := find_index_block(lines); RAISE FileError if missing
    entries, _ := parse_entries(lines)
    new_end := begin + 3 + |entries|         # 0-indexed END line after rewrite (header + self + E)
    delta := new_end - end                   # the single constant shift
    rows := [ [LLT_INDEX_BLOCK, "—","—","—","—","—", begin+1, new_end+1] ]   # self-row
    for e in entries:
        rows += [ e.id, title|"—", Category|"—", Severity|"—", Status|"—", Recorded|"—",
                  e.start + delta, e.end + delta ]    # DEV(6): em-dash placeholder; DEV(7): final e.end
    return [HEADER] + rows

index_is_fresh(text) -> bool
    (begin, end) := find_index_block(lines); if missing: return false
    return lines[begin+1 .. end) == expected_index_rows(text)

regenerate(text) -> text'
    new_lines := lines[:begin+1] + expected_index_rows(text) + lines[end:]   # keeps both markers
    return join(new_lines)            # DEV(5): any write emits LF

init(path, force)
    if path does not exist: atomic_write(build_template()); print "init: created {path}"; return 0
    (begin, _) := find_index_block(text.lines)
    if begin == none:                 # not a lessons record
        if not force: RAISE FileError "{path} exists but is not a LESSONS_LEARNED.md file; refusing to overwrite. Re-run with --force to replace it."
        atomic_write(build_template()); print "init: replaced non-LLT file at {path} with template (--force)"; return 0
    # DEV(2): a lessons record is NEVER overwritten, even with --force — lessons are data
    errors := structural_errors(text)
    if errors: print each to stderr; return 2
    print "init: {path} already initialized ({n} lessons); nothing to do"; return 0

add(file, args)
    if path does not exist: RAISE FileError "{path} does not exist; run `init` first"
    errors := structural_errors(text); if errors: print each; return 2
    args.recorded := args.recorded or today()            # default applied BEFORE validation
    validate_add_args(args)    # title/context/pitfall/solution non-empty, single-line, tab-free;
                               # category/severity in vocab; recorded matches DATE_RE; optional values tab-free
    if args.supersedes:
        if not ID_RE.match(args.supersedes): RAISE InputError "--supersedes '{v}' must be an LLT-NNNN id (G7)"
        target := entry with that id, else RAISE InputError "--supersedes {id}: no such entry (G7)"
        if target.Status != "active": RAISE InputError "--supersedes {id}: that entry is not active; supersede the newest replacement instead (G7)"
        flip the first "- **Status:**" line inside lines[target.start-1 .. target.end) to "- **Status:** superseded"
    if args.id:
        if not ID_RE.match(args.id): RAISE InputError "--id '{v}' must match LLT-[0-9]{4} (G4)"
        if args.id in entries: RAISE InputError "--id {id} already exists; ids are never reused (G4)"
        if int(args.id[4:]) <= max_id(entries): RAISE InputError "--id {id} must be greater than the current maximum LLT-{max:04d}; entries are appended in id order (G4)"
        entry_id := args.id
    else: entry_id := "LLT-" + (max_id + 1) zero-padded to 4
    new_text := text.rstrip("\n") + "\n\n" + render_entry(args, entry_id) + "\n"
    new_text := regenerate(new_text)
    if structural_errors(new_text) non-empty: print each; RAISE FileError "internal error: generated file is invalid; file not written"
    if not index_is_fresh(new_text): RAISE FileError "internal error: index not fresh after add; file not written"
    atomic_write(path, new_text)
    print "add: recorded {entry_id} — {title}"; print "add: index updated ({path})"; return 0

sync(path)
    structural OK? (else print each error, return 2)
    new_text := regenerate(text)
    if new_text == text: print "sync: index already current ({path})"
    else: atomic_write; print "sync: index regenerated ({path})"
    return 0

check(path)
    structural OK? (else print each error, return 2)
    if not index_is_fresh(text): RAISE StaleIndex "{path}: index is stale; run `sync` to regenerate"   # exit 1
    print "check: {path} is valid ({n} lessons recorded)"; return 0

next-id(path)
    structural OK? (else print each error, return 2)
    print "LLT-{max_id + 1:04d}"; return 0

main(argv) -> int                          # DEV(2): returns int; `__main__` does sys.exit(main())
    args := parse(argv)    # subparsers required; defaults: category=other, severity=medium, recorded=None
    try: return command(args)
    except FileError | InputError as exc: print "manage_lessons: {exc}" to stderr; return 2
    except StaleIndex as exc: print "manage_lessons: {exc}" to stderr; return 1
```

<!-- SECTION:WALKTHROUGH -->
## 4. Walk-through (plain English)

### 4.1 Step-by-step

1. **Create** the record: `init` writes a 14-line template — title, intro
   prose, the index block (BEGIN, TSV header, one self-row, END) — and
   refuses to clobber anything that already looks like a lessons record, even
   with `--force`; only a *non-LLT* file can be replaced, and only with
   `--force`.
2. **Record** a lesson: `add` first proves the existing file is valid
   (structure + fields + vocabularies + supersession + id order). It then
   validates the new lesson's inputs, optionally flips the target's `Status`
   line to `superseded` (only when the target exists and is still active),
   assigns the id (explicit `--id` must be unused and greater than the
   current maximum; otherwise `max + 1`), appends the 13-line entry,
   regenerates the index, re-validates the *generated* text (structure and
   freshness), and only then writes atomically.
3. **Heal** drift: `sync` regenerates the block; if nothing changed it says
   so and writes nothing.
4. **Gate**: `check` re-runs the whole validation and additionally requires
   the stored index to equal the derived one — stale is exit 1, malformed is
   exit 2, clean is exit 0 with the lesson count.
5. **Navigate**: `next-id` prints the smallest legal id, so agents never
   guess ids.

### 4.2 Worked example

Every number below was replayed against the pinned script this session
(`worked.py` harness, identical outputs).

**Step 1 — `init`.** 14-line file:

```
 1 | # Lessons Learned
 2 |
 3 | Authoritative record of lessons learned during the development of this system:
 … | (intro prose, lines 3–9)
10 |
11 | <!-- LLT:INDEX:BEGIN -->
12 | id	title	category	severity	status	recorded	start_line	end_line
13 | LLT_INDEX_BLOCK	—	—	—	—	—	11	14
14 | <!-- LLT:INDEX:END -->
```

`begin = 10`, `end = 13` (0-indexed); zero entries → `new_end = 10 + 3 + 0 =
13`, `delta = 0`; self-row = (11, 14) — BEGIN and END lines, exactly as
printed. `check` → `0 lessons recorded`; `next-id` → `LLT-0001`.

**Step 2 — `add --title "First lesson" --context … --pitfall … --solution …`.**
Pre-rewrite: 28 lines (14 template + 1 blank + 13 entry lines), entry marker
on line 16, last field on line 28. Because the text ends with a newline,
`split("\n")` yields 29 elements (phantom `""` at index 28), so the entry
span is `start = 16`, `end = 29` (DEV(7)). Regeneration: `new_end = 10 + 3 +
1 = 14`, **`delta = 1`**; rows become self (11, 15) and LLT-0001 (17, 30).
Post-rewrite file is **29 lines**; the entry sits at lines 17–29 (marker 17,
heading 18, fields 20–29). Note the row's `end = 30` = actual last line (29)
+ 1 — the phantom-line overshoot of DEV(7). `next-id` → `LLT-0002`.

**Step 3 — `add --title "Replacement lesson" … --supersedes LLT-0001`.**
The flip rewrites line 23 (`- **Status:** active` → `superseded`) inside the
target span (16…29 in the pre-rewrite file); nothing outside it changes.
LLT-0002 appends after a blank line: pre-rewrite 43 lines, marker on line
32. Regeneration: `new_end = 10 + 3 + 2 = 15`, `delta = 1`; final file is
**44 lines**:

```
13 | LLT_INDEX_BLOCK	—	—	—	—	—	11	16
14 | LLT-0001	First lesson	other	medium	superseded	2026-10-18	18	31
15 | LLT-0002	Replacement lesson	other	medium	active	2026-10-18	32	45
16 | <!-- LLT:INDEX:END -->
…  | 18: LLT-0001 marker, 24: its Status line now reads "superseded"
…  | 32: LLT-0002 marker, 42: "- **Supersedes:** LLT-0001", 44: last field
```

Check the invariant end-to-end: LLT-0001's row span (18–31) ends at the blank
line before marker 2 (interior entries are span-inclusive); LLT-0002's span
(32–45) ends one past EOF (final entry, DEV(7)); the bidirectional
supersession holds (LLT-0002 points at LLT-0001, and LLT-0001 is the only
`superseded` entry). `check` → exit 0, `2 lessons recorded`; `next-id` →
`LLT-0003`; a second `add --supersedes LLT-0001` would be rejected with
`that entry is not active; supersede the newest replacement instead (G7)`.

<!-- SECTION:IMPLEMENTATION -->
## 5. Implementation notes (entry-level guide)

### 5.1 Data structures

- **`Entry`** (dataclass): `id: str`, `title: str`, `fields: dict[str, str]`,
  `start: int` (1-indexed marker line), `end: int` (0-indexed index of the
  *next* marker — numerically the 1-indexed inclusive last line, **except**
  for the final entry, where it is one past the file's last line because of
  the phantom `""` split element — DEV(7)). Mutable; the commands treat it
  as read-only.
- **Exceptions:** `FileError` (malformed file / unsafe operation → 2),
  `StaleIndex` (derived ≠ stored → 1), `InputError` (rejected `add` input →
  2). `main()` is the only translator to exit codes (DEV(2)).
- **`atomic_write`:** `tempfile.NamedTemporaryFile` in the *target* directory
  (same filesystem — `os.replace` is atomic only then) + `os.replace`; the
  temp file is unlinked on any failure path.
- **Regexes** (module level, compiled once): `BEGIN_RE`/`END_RE` tolerate
  inner whitespace; `ENTRY_MARKER_RE` = `^<!--\s*LLT:ENTRY:(LLT-(?a:\d){4})\s*-->\s*$`;
  `HEADING_RE` = `^##\s+(LLT-(?a:\d){4})\s+—\s+(\S+(?:\s+\S+)*)\s*$` — the em dash is
  *required*; `FIELD_RE` = `^-\s+\*\*([A-Za-z]+):\*\*\s*(\S*(?:\s+\S+)*)\s*$` (colon
  inside the bold, value may be empty).
- **Vocabularies:** 11 categories, 4 severities, 2 statuses — closed sets
  (guard G6); never extend by "fixing" an error message.

### 5.2 Edge cases and defined behavior

All rows verified against the pinned script this session (harnesses
`worked.py`, `verify_b3.py`, `verify_l21.py`, `verify_l22.py`).

| Case | Defined behavior | Why |
|---|---|---|
| `init` on a missing path | exit 0, `init: created {path}`; 14-line template, self-row (11, 14) | fresh record |
| `init` on an existing valid LLT file (with or without `--force`) | exit 0, `init: … already initialized (N lessons); nothing to do`; file byte-identical | lessons are data — never overwritten (DEV(2)) |
| `init` on a non-LLT file | exit 2, `refusing to overwrite. Re-run with --force to replace it.`; with `--force`: exit 0, `init: replaced non-LLT file … (--force)` | data-loss guard |
| `add`/`sync`/`check`/`next-id` on a missing file | exit 2, `{path} does not exist; run `init` first` | fail closed |
| `add` with missing/blank required arg | exit 2 (argparse usage or `--{name} is required and must be non-empty (G6)`) | G6 |
| `add --category banana` | exit 2, `--category 'banana' not in vocabulary: … (G6)` | closed vocabulary |
| `add --recorded 2026-99-99` | **accepted** — entry carries `2026-99-99`, `check` exit 0 | `DATE_RE` is format-only (DEV(3)) |
| `add --recorded 2026-1-1` | exit 2, `--recorded '2026-1-1' is not YYYY-MM-DD (G6)` | shape guard |
| `next-id` on fresh record / after `--id LLT-0005` add | `LLT-0001` / `LLT-0006` | smallest legal id |
| `add --id` duplicate | exit 2, `--id … already exists; ids are never reused (G4)` | citation stability |
| `add --id` ≤ current max | exit 2, `--id … must be greater than the current maximum LLT-NNNN; entries are appended in id order (G4)` | append order |
| `add --supersedes` unknown id | exit 2, `--supersedes LLT-9999: no such entry (G7)` | invariant |
| `add --supersedes` active entry | exit 0; exactly one `- **Status:** superseded` line; new entry's `Supersedes` = target | bidirectional invariant (I3) |
| `add --supersedes` already-superseded entry | exit 2, `that entry is not active; supersede the newest replacement instead (G7)` | chain integrity |
| Duplicate entry marker | exit 2, `duplicate entry marker LLT-NNNN (line N); ids must be unique (G4)` | G4 |
| Ids not strictly increasing | exit 2, `entry ids must strictly increase in file order (append-only); found A followed by B (G4)` (first violation only) | G4 |
| Marker id ≠ heading id | exit 2, `entry marker … disagrees with heading id …; marker and heading must match (G8)` | G8 |
| Tab in a field value / title | exit 2, `… contains a tab character (G6)` | TSV cells must be tab-free |
| Empty optional field (`- **Prevention:**`) | exit 2, `optional field 'Prevention' is empty; write — when absent (G6)` | G6 |
| Empty required field | exit 2, `required field 'Pitfall' is empty (G6)` | G6 |
| Missing required field line | exit 2, `missing required field 'Pitfall' (G6)` | G6 |
| Out-of-vocabulary field value | exit 2, e.g. `Severity 'urgent' not in vocabulary: low, medium, high, critical (G6)` | G6 |
| Entry marker before the index block | exit 2 (FileError), `entry marker at line N appears before the index block; the index must be first (G8)` | I1 |
| Second BEGIN/END pair later in file | body text: last row's end changes → `check` exit 1 (stale); `sync` exit 0 (regenerates first block only); pair survives; `check` exit 0 again | `find_index_block` stops at first END (see `line-index-sync.md` DEV(3)) |
| Same-line body edit (e.g. rewrite `Context`) | `check` exit **0** — NOT stale | body content is not indexed (DEV(4)) |
| Line-count change in an entry | `check` exit 1, `… index is stale; run `sync` to regenerate`; `sync` exit 0; `check` exit 0 | geometry is indexed (DEV(4)) |
| Indexed-field change (e.g. `Severity` medium → high) | `check` exit 1 (stale); `sync` heals | fields are indexed (DEV(4)) |
| CRLF file, `check` | exit 0 | universal-newline read (DEV(5)) |
| CRLF file, fresh `sync` | `sync: index already current`; **no write** — on-disk CRLF preserved (byte-verified) | DEV(5) |
| CRLF file, `add` or stale `sync` | output normalized to LF | any actual write emits LF (DEV(5)) |
| `sync` on a fresh file | exit 0, `sync: index already current ({path})`, no write | idempotence (§2.3) |

### 5.3 Invariants and how to test them

1. **Block first and unique** (I1). Test: entry marker on line 1 → exit 2
   "appears before the index block".
2. **Entry well-formedness** (I2). Test: each G6/G8 violation in §5.2 →
   exit 2 with the field named.
3. **Supersession bidirectionality** (I3). Test: `add --supersedes` on an
   active entry leaves exactly one `superseded` line and a matching
   `Supersedes` row; superseding the superseded entry is rejected.
4. **Append order** (I4). Test: hand-transposed markers → exit 2
   "strictly increase".
5. **Derived index** (I5). Test: `sync` twice → second run "already current",
   bytes unchanged; `check` exit 0 after any `add`.
6. **`add` never writes invalid text.** Test (internal): the two
   "internal error" FileErrors are the only post-generation guard — a test
   can simulate by monkeypatching `regenerate` to drop a row and asserting
   no file write (proposed; not yet run).

### 5.4 Pitfalls and known traps

- **`main(argv)` takes argv *without* the program name**, and `main`
  **returns** the exit code — it does not `sys.exit` (DEV(2)). In-process
  harnesses must assert the return value; subprocess harnesses get the code
  for free.
- **The phantom line** (DEV(7)): `text.split("\n")` on text ending in `\n`
  leaves a trailing `""`; the final entry's `end` (and therefore the row's
  `end_line`) is one past the last real line. Do not "fix" row math to match
  the skill spec without a doc-first change — the pinned behavior is what
  `check` compares against.
- **`HEADING_RE` requires the em dash.** `## LLT-0001 - title` (hyphen) does
  not match → "missing heading" error, not a title parse.
- **`Recorded` default happens before validation:** `args.recorded =
  args.recorded or today()` runs before `validate_add_args`; the default is
  therefore always legal, and an explicit bad value still fails (L7b).
- **Supersession flip scope:** the flip scans `lines[target.start − 1 ..
  target.end)` for the first `- **Status:**` line and stops — it cannot touch
  another entry (I1), but a hand-edited file with a stray `Status:` line
  inside the span would be the flip target.
- **Errors are collected, not fail-fast** (`parse_entries`/
  `check_consistency`): one `check` can print several lines — a hook that
  greps for a single error string will see the first, not "the" error.
- **O(E²) supersession scan** is intentional simplicity at record scale;
  don't optimize it without a size that needs it (§2.4).
- **`filterwarnings = ["error"]`** in the repo's pytest config: the B3
  package port must be warning-clean.
- **Vocabulary changes require a doc-first change** (G6): extend
  `CATEGORIES`/`SEVERITIES`/`STATUSES` only via the algorithm-document
  cycle, never to silence an error.

### 5.5 Language notes

- Python 3.10+ (`zip(..., strict=False)` is used for the id-order scan).
- `datetime.date.today().isoformat()` supplies the `Recorded` default —
  the one environment-dependent value in an otherwise pure core.
- `dataclass` with `field(default_factory=dict)` for `Entry.fields` (mutable
  default).
- Atomicity relies on `os.replace` semantics: the temp file must share the
  destination's directory/filesystem — hence `dir=directory` in
  `NamedTemporaryFile`.
- The B3 package port keeps the pure functions on `text` + this exception
  hierarchy, moves file I/O/messages/exit codes into one command layer, and
  replaces the argparse `args` object in `render_entry` with a typed
  `NewLesson` dataclass (behavior-preserved; see BACKLOG B3).

<!-- SECTION:TESTS -->
## 6. Test cases and sample data

All sample data is synthetic (temp directories under `/var/folders/…`).
"verified" = replayed against the pinned script at `ad0fc9f` this session
(harnesses `worked.py`, `verify_b3.py`, `verify_l21.py`, `verify_l22.py`);
"existing" = already in `tests/scripts/test_skill_scripts.py`.

| # | Name | Input (sample data) | Expected output | Why it matters |
|---|---|---|---|---|
| L1 | init fresh (verified) | `init tmp/LESSONS_LEARNED.md` | exit 0, `init: created …`; 14-line template; self-row (11, 14); `check` → 0, `… is valid (0 lessons recorded)` | happy path (G5) |
| L2 | init idempotent (verified) | `init` again on the L1 file | exit 0, `init: … already initialized (0 lessons); nothing to do`; file byte-identical | lessons never clobbered (DEV(2)) |
| L3 | init refusal (verified) | `init` over a plain `# notes` file | exit 2, `… refusing to overwrite. Re-run with --force to replace it.`; with `--force`: exit 0, `init: replaced non-LLT file … (--force)` | data-loss guard |
| L4 | add missing file (verified) | `add tmp/nope.md --title …` | exit 2, `… does not exist; run `init` first` | fail closed |
| L5 | add missing required arg (verified) | `add` without `--solution` | exit 2 (argparse usage error) | G6 |
| L6 | add out-of-vocab category (verified) | `add --category banana` | exit 2, `--category 'banana' not in vocabulary: … (G6)` | closed vocabulary |
| L7a | format-only date (verified) | `add --recorded 2026-99-99` | **accepted** — entry carries `2026-99-99`; `check` exit 0 | DEV(3) pinned |
| L7b | bad date shape (verified) | `add --recorded 2026-1-1` | exit 2, `--recorded '2026-1-1' is not YYYY-MM-DD (G6)` | shape guard |
| L8 | next-id fresh (verified) | `next-id` on L1 file | stdout `LLT-0001` | smallest legal id |
| L9 | explicit id gap (verified) | `add --id LLT-0005 …` then `next-id` | exit 0; `next-id` → `LLT-0006` | `--id` contract |
| L10 | duplicate id (verified) | `add --id LLT-0001` when LLT-0001 exists | exit 2, `--id LLT-0001 already exists; ids are never reused (G4)` | G4 |
| L11 | id ≤ max (verified) | `add --id LLT-0004` when max is LLT-0005 | exit 2, `--id LLT-0004 must be greater than the current maximum LLT-0005; entries are appended in id order (G4)` | G4 |
| L12 | supersedes unknown (verified) | `add --supersedes LLT-9999` | exit 2, `--supersedes LLT-9999: no such entry (G7)` | I3 |
| L13a | supersedes active (verified) | `add … --supersedes LLT-0001` (active) | exit 0; exactly one `- **Status:** superseded` line; new entry's `Supersedes: LLT-0001`; `check` 0 | I3; flip locality |
| L13b | supersedes superseded (verified) | `add … --supersedes LLT-0001` (already superseded) | exit 2, `that entry is not active; supersede the newest replacement instead (G7)` | chain integrity |
| L13c | malformed supersedes value (existing, `test_bad_supersedes_value_rejected`) | `- **Supersedes:** LLT-1` | `check` exit 2 with **both** (in order): `Supersedes 'LLT-1' must be an LLT-NNNN id or — (G7)`, then `Supersedes LLT-1, which does not exist (G7)` | the shape guard and the existence guard are independent — a malformed value fires both |
| L14 | duplicate marker (verified) | two `<!-- LLT:ENTRY:LLT-0001 -->` lines | `check` exit 2, `duplicate entry marker LLT-0001 (line N); ids must be unique (G4)` | G4 |
| L15 | ids not increasing (verified) | LLT-0002 marker before LLT-0001 marker | `check` exit 2, `entry ids must strictly increase in file order (append-only); found 2 followed by 1 (G4)` | G4 |
| L16a | tab in field (verified) | `Context` value containing a tab | `check` exit 2, `entry LLT-0001: field 'Context' contains a tab character (G6)` | TSV integrity |
| L16b | empty optional (verified) | `- **Prevention:**` (empty) | `check` exit 2, `optional field 'Prevention' is empty; write — when absent (G6)` | G6 |
| L17 | missing required (verified) | `Pitfall` line deleted | `check` exit 2, `missing required field 'Pitfall' (G6)` | G6 |
| L17b | empty required (verified) | `- **Pitfall:**` (empty) | `check` exit 2, `required field 'Pitfall' is empty (G6)` | G6 |
| L17c | out-of-vocab severity (verified) | `Severity: urgent` | `check` exit 2, `Severity 'urgent' not in vocabulary: low, medium, high, critical (G6)` | G6 |
| L17d | marker/heading mismatch (verified) | marker `LLT-0001`, heading `## LLT-0002 — T1` | `check` exit 2, `entry marker LLT-0001 (line 17) disagrees with heading id LLT-0002 (line 18); marker and heading must match (G8)` | G8 |
| L17e | marker before block (verified) | `<!-- LLT:ENTRY:LLT-0001 -->` on line 1 | `check` exit 2, `entry marker at line 1 appears before the index block; the index must be first (G8)` | I1 |
| L18 | sync idempotent (verified) | `sync` on a fresh file | exit 0, `sync: index already current (…)`; no write | I5 |
| L19a | body line-count change (verified) | one line appended inside an entry | `check` exit 1, `… index is stale; run `sync` to regenerate`; `sync` 0; `check` 0 | DEV(4): geometry is indexed |
| L19c | indexed-field change (verified) | `Severity` `medium` → `high` | `check` exit 1 (stale); `sync` heals | DEV(4) |
| L19d | same-line body edit (verified) | rewrite `Context` text in place | `check` exit **0** — NOT stale | DEV(4): body content is not indexed |
| L20a | CRLF check (verified) | CRLF-encoded record (byte-verified) | `check` exit 0 | DEV(5) |
| L20b | CRLF no-write (verified) | `sync` on the L20a file | `sync: index already current`; disk bytes unchanged (CRLF preserved); `add`/stale-`sync` emit LF | DEV(5); LLT-0011 |
| L21 | second index pair (verified) | fresh 1-entry record + appended second BEGIN/END pair | `check` exit 1 (stale — last row's end changed); `sync` exit 0; `check` exit 0; the pair survives as body text | `find_index_block` stops at first END (cf. `line-index-sync.md` DEV(3)) |
| W1 | full lifecycle (verified — §4.2) | `init` → `add "First lesson"` → `add "Replacement lesson" --supersedes LLT-0001` | exact line math of §4.2: 14 → 29 → 44 lines; rows (17, 30) then (18, 31)/(32, 45); `check` 0; `next-id` `LLT-0003` | end-to-end replay; pins DEV(7) overshoot |

### 6.1 Property tests (optional but preferred)

- **Idempotence:** for any well-formed `t`, `sync(sync(t)) == sync(t)` (bytes).
- **Freshness:** `check` exits 0 on every output of `init`, `add`, `sync`.
- **Supersession closure:** in any `check`-passing file, `{e : Status(e) =
  superseded} == {t : ∃ e, Supersedes(e) = t}` (I3 both directions).
- **Append order:** in any `check`-passing file, id suffixes strictly
  increase in file order (I4).
- **No-write guarantee:** `add` that rejects its input leaves the file
  byte-identical.

### 6.2 Performance acceptance

O(L)/O(E²) claims are not load-bearing at record scale (this record: 8
entries; realistic ceiling: a few hundred). No budget set; a 50k-line record
with 5k entries should `check` in well under a second on a laptop-class
machine (claimed, unverified).

<!-- SECTION:REFERENCES -->
## 7. References

- `scripts/manage_lessons.py` at `mirph-glitch42/SecureTrace@ad0fc9f` (pinned implementation, 674 lines).
- `tests/scripts/test_skill_scripts.py` — existing contract tests (subprocess-based; pin init/add roundtrip and `next-id`).
- Skill `learned-lesson-tracker`: `references/entry-anatomy.md` (the file/field contract), `references/guards.md` (G1–G9; the script enforces G4–G8), `references/template.md`, `references/example-lessons.md`.
- `algorithms/line-index-sync.md` — the shared delta core (third format here); cross-referenced deviations DEV(1)/(3)/(5)/(6).
- `LESSONS_LEARNED.md` — LLT-0002 (vendoring decision), LLT-0009 (priority-regex mismatch, sibling format), LLT-0010 (staleness semantics, DEV(4)), LLT-0011 (universal-newline reads, DEV(5)).
- `Makefile` `docs-check` gate — runs `manage_lessons.py check LESSONS_LEARNED.md` in CI.
