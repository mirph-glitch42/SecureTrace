# Workflow-YAML Strict Parse (duplicate mapping-key detection for CI workflows)

<!-- INDEX:BEGIN format=tsv version=1 -->
id	start_line	end_line
INDEX_BLOCK	3	13
METADATA	15	36
THEORY	37	77
PSEUDOCODE	78	132
WALKTHROUGH	133	161
IMPLEMENTATION	162	207
TESTS	208	231
REFERENCES	232	238
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Workflow-YAML Strict Parse (duplicate mapping-key detection for CI workflows) |
| Slug | workflow-yaml-strict-parse |
| Version | 0.1.0 |
| Status | draft |
| Author | SecureTrace (mirph-glitch42) |
| Created | 2026-10-19 |
| Last modified | 2026-10-19 |
| Status history | 0.1.0 (2026-10-19): initial draft (document-before-code, B8) |
| Languages | Python 3 (reference implementation); algorithm is language-agnostic |
| Implementation location | — (filled when the implementation lands, B8) |
| Time complexity | O(N) per file (N = YAML node count) — one parse pass, duplicate scan linear in pairs |
| Space complexity | O(N) — PyYAML node tree + one per-mapping `seen` set (freed on unwind) |
| Determinism | deterministic |
| Dependencies | <br>PyYAML ≥ 6 (pinned + hashed in `requirements-dev.txt`) |
| Thread safety | pure core is thread-safe (no shared state); file I/O is caller-serialized |
| Related documents | <br>`LESSONS_LEARNED.md` entry LLT-0017 (duplicate YAML keys: local parsers tolerate, GitHub hard-fails)<br>`LESSONS_LEARNED.md` entry LLT-0018 (0-job fallback-name run = definition parse error)<br>BACKLOG.md item B8 (this gate is its deliverable) |

<!-- SECTION:THEORY -->
## 2. Theory

### 2.1 Problem definition

GitHub Actions validates workflow files with its own YAML parser (yaml.v3), which **hard-fails the entire workflow on duplicate mapping keys** in one mapping — while the common local parsers (PyYAML, Ruby Psych) **silently tolerate** them (last value wins). Consequence: a workflow that parses cleanly in local tooling can ship to GitHub and produce zero jobs (B5 incident: duplicate `attestations:` key under `permissions`; `Release` run 39234156533, LLT-0017/LLT-0018).

This algorithm defines a **strict local parse**: given a set of YAML workflow files, report every duplicate mapping key with file + key + 1-based line, plus any parse error, under a three-state exit contract:

- **Input:** a list of file paths — explicit arguments, or the default discovery set `.github/workflows/*.yml` + `.github/workflows/*.yaml`.
- **Output:** exactly one line per file: `✓ <path> OK` or `✗ <path>: <finding>`; a finding is `duplicate key '<k>' at line <n>` (n = 1-based line of the **second**, colliding occurrence) or `parse error: <message>`.
- **Exit:** `0` = all files clean; `1` = ≥1 duplicate-key finding or parse error; `2` = usage or environment error (no files found by default discovery, missing/unreadable explicit file, PyYAML not installed).
- **Forbidden:** silently accepting duplicates (that is the defect being closed); mutating the input files.
- **Undefined:** non-UTF-8 input (the reference reads UTF-8 and reports a decode failure as a parse error, exit-1 class).

### 2.2 Why this approach

**Chosen: strict `SafeLoader` subclass overriding the mapping constructor.** PyYAML dispatches one constructor (`construct_mapping`) for *every* mapping node — block, flow, and nested — so a single override installs the duplicate check on the whole parse tree in one pass, with exact node positions (`start_mark`) for reporting. `SafeLoader` (not `FullLoader`/`UnsafeLoader`) keeps construction limited to plain data types: a gate must never execute arbitrary code while reading YAML it does not control.

**Rejected: line-based key scanner (regex on `^\s*<key>:`).** Cannot see flow mappings (`{a: 1, a: 2}`), quoted keys, anchors/aliases, or nested duplicates at the right scope, and false-positives on key-like text inside strings and comments.

**Rejected: `yaml.safe_load` + post-hoc comparison.** PyYAML merges duplicate keys into one mapping *during construction* — by the time the dict exists the evidence is gone (last value wins). Detection must happen inside construction.

**Rejected: Ruby Psych.** Not present in the venv or CI runners, and adding a runtime dependency the DevSecOps gate cannot pin/hash is not acceptable.

### 2.3 Correctness argument

Invariant **I1 (every mapping node is visited):** PyYAML's constructor dispatch invokes the loader's `construct_mapping` exactly once per mapping node in the parse tree — block and flow mappings alike, nested mappings by recursion (`deep=True`). One override on the loader class therefore installs the duplicate check on all mapping nodes; there is no per-node hooking and no missed nesting level.

Invariant **I2 (duplicate ⟺ key collision within one node's pair list):** for a mapping node with pairs `(k₁,v₁)…(kₙ,vₙ)`, the mapping is invalid under the GitHub parser iff some `kᵢ = kⱼ` for `i < j` (equality of the constructed key values). The override scans the pair list in document order with a `seen` set and raises on the first `kⱼ ∈ seen`; it therefore raises iff I2 holds, and the reported line is the `start_mark` of `kⱼ` — the colliding (second) occurrence. ∎

**Exit-code contract:** the usage phase (file list, readability, dependency) runs before any parse and maps failures to exit 2; per-file findings and parse errors map to exit 1; a clean sweep maps to exit 0. Parse errors (scanner/parser/composer) are findings, not usage errors, because the file exists and is a malformed workflow — precisely the class GitHub rejects. ∎

### 2.4 Complexity

One PyYAML parse per file: O(N) time and space, N = node count (PyYAML builds the full node tree; construction is linear in nodes). The duplicate scan adds O(m) per mapping node (m = its pair count), summing to O(N) overall — no iteration to a fixed point, no quadratic step. (Claimed; consistent with PyYAML's single-pass parse. Workflow files are tens of nodes, so no benchmark is load-bearing — see 6.2.)

### 2.5 Deviations

none — documented before implementation.

<!-- SECTION:PSEUDOCODE -->
## 3. Pseudocode

```
# Contract: check_file(path) -> (ok: bool, detail: str)
#   ok = true  -> detail is ""
#   ok = false -> detail = "duplicate key '<k>' at line <n>"
#                 or "parse error: <first line of the YAML error>"

DuplicateKeyError (a kind of YAMLError)
  fields: key, line   # the colliding key; 1-based line of that key node

class StrictLoader extends SafeLoader:
  # PyYAML invokes this exactly once per mapping node (block, flow, nested) — I1.
  construct_mapping(node, deep):
    seen := empty set of constructed keys
    out  := empty mapping
    for (key_node, value_node) in node.value in document order:   # single pass, O(pairs)
      key := construct_object(key_node, deep)    # scalar: str/bool/int/float/null
      if key in seen:                            # I2: collision -> hard fail
        raise DuplicateKeyError(key, key_node.start_mark.line + 1)   # start_mark is 0-based
      seen.add(key)
      out[key] := construct_object(value_node, deep)
    return out

check_file(path):
  try:
    text := read(path, utf-8)                    # decode failure -> parse-error finding
    safe_load(text, Loader = StrictLoader)
    return (true, "")
  catch DuplicateKeyError as d:
    return (false, "duplicate key '" + string(d.key) + "' at line " + d.line)
  catch YAMLError as e:                          # scanner/parser/composer: malformed YAML
    return (false, "parse error: " + first_line(e))

main(argv):
  if importing PyYAML fails:                     # environment problem, not content
    print("PyYAML required — install pinned deps (make setup)"); return 2
  files := argv.files
  if files is empty:
    files := sorted(glob(".github/workflows/*.yml") + glob(".github/workflows/*.yaml"))
    if files is empty:
      print("no workflow files found in .github/workflows/"); return 2
  for f in files:
    if f is not a readable regular file:         # usage phase precedes parse phase
      print("missing or unreadable file: " + f); return 2
  findings := 0
  for f in files in order:
    (ok, detail) := check_file(f)
    if ok: print("✓ " + f + " OK")
    else:  print("✗ " + f + ": " + detail); findings += 1
    # one file's failure never stops the rest — report every file
  return (findings == 0) ? 0 : 1
```

<!-- SECTION:WALKTHROUGH -->
## 4. Walk-through (plain English)

### 4.1 Step-by-step

1. **Usage phase (exit-2 class).** Decide the file list: explicit arguments, or default discovery over `.github/workflows/` (both `.yml` and `.yaml`, sorted so output order is deterministic). Zero discovered files, or any explicit file missing/unreadable → report and stop with exit 2. If PyYAML itself is missing, stop with exit 2 before touching any file.
2. **Parse phase (exit-1 class).** For each file, parse with the `StrictLoader`. PyYAML builds the full node tree, then constructs values; construction visits every mapping node through the overridden `construct_mapping` (I1).
3. **Duplicate check (per mapping).** As each mapping's pairs are constructed in document order, every constructed key goes into a `seen` set. A key already in `seen` is a duplicate: raise `DuplicateKeyError` carrying the key and the colliding key node's 1-based line. The exception aborts construction for that file only.
4. **Report.** Each file prints exactly one line — `✓ <path> OK` or `✗ <path>: duplicate key 'k' at line N` (or `parse error: …` for malformed YAML). Exit 1 if any file failed, 0 otherwise.

### 4.2 Worked example

Input `release.yml` (minimal shape of the B5 incident):

```yaml
permissions:
  contents: read
  attestations: write
  attestations: read
on: push
```

1. Usage phase: one explicit file, readable → proceed.
2. Parse: node tree = one top-level mapping; the `permissions` value is a mapping with pairs `contents`, `attestations`, `attestations`.
3. Constructing the `permissions` mapping: `contents` → seen={contents}; first `attestations` → seen={contents, attestations}; second `attestations` → already in seen → raise `DuplicateKeyError(key="attestations", line=4)` (line 4 = the colliding key's 1-based line).
4. Report: `✗ release.yml: duplicate key 'attestations' at line 4`; exit 1. The top-level mapping never completes — the same all-or-nothing rejection GitHub's parser performs (LLT-0018: the run appears with a fallback name and 0 jobs).

Contrast: plain `yaml.safe_load` on the same text silently returns `permissions: {contents: read, attestations: read}` — last value wins, nothing reported. That divergence between local and GitHub parsers is the exact defect this gate closes (LLT-0017).

<!-- SECTION:IMPLEMENTATION -->
## 5. Implementation notes (entry-level guide)

### 5.1 Data structures

- `DuplicateKeyError(yaml.YAMLError)` — carries `key` (the constructed key object) and `line` (int, 1-based). Subclassing `YAMLError` keeps it in the parse-failure family; it is caught *before* the generic `YAMLError` handler so the message stays specific.
- `StrictLoader(yaml.SafeLoader)` — one override: `construct_mapping(loader, node, deep=False)`. The override must call `loader.construct_object(key_node, deep=deep)` exactly as PyYAML's default does, so key construction (str/bool/int/float/null) matches `safe_load` semantics.
- No other state: the `seen` set is local to one mapping node and freed on unwind.

### 5.2 Edge cases and defined behavior

| Case | Defined behavior | Why |
|---|---|---|
| clean file (no duplicates, valid YAML) | `✓ <path> OK`; contributes to exit 0 | happy path |
| duplicate top-level key | `✗ … duplicate key 'k' at line N` (N = second occurrence); exit 1 | the B5 incident shape |
| duplicate nested key (any depth) | same; N = colliding key's line | I1: every mapping node is visited |
| flow-style duplicate (`{a: 1, a: 2}`) | same; N = line of the second `a` | flow mappings use the same constructor |
| same key in *different* mappings (e.g. two jobs each with `steps`) | not a duplicate; passes | `seen` is per mapping node (I2), never global |
| malformed YAML (bad indent, unterminated flow) | `✗ … parse error: <msg>`; exit 1 | malformed workflow = content finding, not usage |
| empty file | `✓ OK` (YAML `null` document) | no mapping, no duplicate possible |
| no files found by default discovery | `no workflow files found in .github/workflows/`; exit 2 | nothing to check is a setup problem |
| explicit file missing/unreadable | `missing or unreadable file: <path>`; exit 2 | usage phase precedes parse phase |
| PyYAML not installed | install hint; exit 2 | environment error, distinct from content findings |

### 5.3 Invariants and how to test them

- **I1 (all mapping nodes visited):** a duplicate at depth ≥ 2 — nested or flow — is reported with the right key and line (table rows 3–4).
- **I2 (duplicate ⟺ collision within one mapping):** the same key appearing in two different mappings passes (table row 5) — a global `seen` set would fail this.
- **Reported line = second occurrence:** tests assert the exact hand-computed line for known fixtures.
- **Exit-code separation:** one test per class — clean → 0; finding/malformed → 1; usage → 2.
- **Output shape:** exactly one line per file, `✓`/`✗`-prefixed; tests assert the exact lines.
- **One failure does not stop the rest:** with two bad files, both are reported (order = argument order).

### 5.4 Pitfalls and known traps

- **Do not `safe_load` + compare dicts** — PyYAML merges duplicates during construction; the evidence is gone by the time the dict exists (§2.2).
- **`construct_mapping` signature:** keep `(loader, node, deep=False)` and honor `deep` in both `construct_object` calls — changing it alters alias/anchor semantics.
- **`start_mark.line` is 0-based** — add 1 before printing; this off-by-one is the classic failure.
- **Non-string keys:** YAML 1.1 (PyYAML) parses `yes`, `on`, `1`, `~` as bool/int/null keys. Duplicate detection compares constructed objects, so `on:` and `yes:` are *different* keys (str vs bool). Do not stringify keys before comparison — that changes semantics.
- **Exit 2 vs 1 boundary:** a file that *exists but is malformed* is exit 1 (content); a file that *does not exist* is exit 2 (usage). Blurring them makes CI triage ambiguous.
- **Deterministic order:** default discovery is sorted; explicit arguments keep argument order. Never use filesystem hash order.

### 5.5 Language notes

Python 3.12 reference: subclass `yaml.SafeLoader`, override `construct_mapping`, raise a `DuplicateKeyError` (`yaml.YAMLError` subclass with `key`/`line` attributes). CLI follows the `scripts/` house style: `sys.argv` (no argparse), explicit exit codes 0/1/2, `✓`/`✗` line output — matching `scripts/backlog_index.py`, `scripts/manage_lessons.py`, `scripts/algorithm_index.py`.

<!-- SECTION:TESTS -->
## 6. Test cases and sample data

| # | Name | Input (sample data) | Expected output | Why it matters |
|---|---|---|---|---|
| 1 | clean file | `name: ci\non: push\njobs:\n  a:\n    steps:\n      - run: x\n` | `✓ <f> OK`, exit 0 | happy path |
| 2 | duplicate top-level key | `on: push\non: pull_request\njobs: {}\n` | `✗ <f>: duplicate key 'on' at line 2`, exit 1 | the B5 incident shape |
| 3 | duplicate nested key | `jobs:\n  a:\n    permissions:\n      contents: read\n      contents: write\n` | `✗ <f>: duplicate key 'contents' at line 4`, exit 1 | I1: nested mappings checked |
| 4 | flow-style duplicate | `jobs: {a: {steps: [{run: x, run: y}]}}\n` | `✗ <f>: duplicate key 'run' at line 1`, exit 1 | flow mappings use the same constructor |
| 5 | same key in different mappings | `jobs:\n  a:\n    steps:\n      - run: x\n  b:\n    steps:\n      - run: y\n` | `✓ OK`, exit 0 | I2: `seen` is per mapping, not global |
| 6 | malformed YAML | `jobs:\n  a:\n   steps: [x\n` | `✗ <f>: parse error: …`, exit 1 | malformed = content finding (1, not 2) |
| 7 | missing explicit file | (nonexistent path) | `missing or unreadable file: …`, exit 2 | usage-phase contract |
| 8 | default discovery on this repo | (no args; `.github/workflows/` = ci.yml + release.yml) | two `✓ … OK` lines, exit 0 | the actual gate: both real workflows must pass |

### 6.1 Property tests (optional but preferred)

- For any file list: exit code ∈ {0, 1, 2} and exactly one output line per file that reached the parse phase.
- For any duplicate at any depth/style: reported key = colliding key; reported line = the *second* occurrence's 1-based line.
- Determinism: repeated runs on the same input list give byte-identical stdout and exit code.

### 6.2 Performance acceptance

Not load-bearing: workflow files are small (tens of nodes); a full default-discovery run must complete in well under 2 s on a laptop-class machine (PyYAML parse cost dominates).

<!-- SECTION:REFERENCES -->
## 7. References

- PyYAML documentation — `yaml.SafeLoader`, `construct_mapping`, `Mark.line` (0-based): <https://pyyaml.org/wiki/PyYAMLDocumentation>
- YAML 1.2 spec (mapping keys must be unique — the rule GitHub enforces): <https://yaml.org/spec/1.2.2/#5-6-mapping-nodes>
- `LESSONS_LEARNED.md` — LLT-0017 (duplicate YAML mapping keys: local parsers tolerate, GitHub hard-fails); LLT-0018 (fallback-name workflow run with 0 jobs means a definition parse error).
- BACKLOG.md — B5 closeout (duplicate-`attestations:` incident, `Release` run 39234156533) and B8 (this gate).
