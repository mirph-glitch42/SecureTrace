# RMF Evidence Bundle (deterministic collection, control mapping, rendering, packaging)

<!-- INDEX:BEGIN format=tsv version=1 -->
id	start_line	end_line
INDEX_BLOCK	3	13
METADATA	15	36
THEORY	37	159
PSEUDOCODE	160	240
WALKTHROUGH	241	295
IMPLEMENTATION	296	405
TESTS	406	439
REFERENCES	440	456
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | RMF Evidence Bundle (deterministic collection, control mapping, rendering, packaging) |
| Slug | rmf-evidence-bundle |
| Version | 0.2.0 |
| Status | draft |
| Author | SecureTrace bootstrap (mirph-glitch42) |
| Created | 2026-10-18 |
| Last modified | 2026-10-19 |
| Status history | 0.1.0 (2026-10-18): initial draft (B4, documented before implementation per G1)<br>0.2.0 (2026-10-19): CLI contract pinned (§5.3); test case 9 added; implementation location extended to command layer + Makefile |
| Languages | Python 3 (reference implementation); algorithm is language-agnostic |
| Implementation location | `src/securetrace/rmf/deliverables.py` (core, B4); `src/securetrace/cli.py` `run_rmf_build` + `src/securetrace/__main__.py` `rmf build` (command layer); `Makefile` `rmf-bundle` target |
| Time complexity | O(T) for `collect` (T = total bytes of the evidence corpus); O(C·E + S) for each renderer (C = control count, E = evidence paths per control, S = state-summary size); O(T + R) for `package` (R = rendered size) |
| Space complexity | O(T + R) — corpus bytes plus rendered documents and manifest held in memory at once |
| Determinism | deterministic — no wall-clock read in the core; fixed/sorted iteration only; canonical JSON; git HEAD is an *input*, not a source of non-determinism |
| Dependencies | <br>Python stdlib only (`hashlib`, `json`, `pathlib`, `subprocess`)<br>`securetrace.backlog.index`, `securetrace.lessons.record`, `securetrace.algorithms.registry` (B3 cores, checkers only) |
| Thread safety | pure core is thread-safe (no shared state); `package()` performs file I/O — caller must serialize |
| Related documents | <br>`algorithms/line-index-sync.md` (the index checks the ST-01/ST-03 checkers reuse)<br>`algorithms/lessons-record.md` (the record checks the ST-02 checker reuses)<br>`docs/dow-requirements.md` (the B2 requirements table this bundle satisfies) |

<!-- SECTION:THEORY -->
## 2. Theory

### 2.1 Problem definition

DoD RMF (DoDI 8510.01, NIST SP 800-37) requires SSP, SAP, SAR, and POA&M for
every system; software below the system level must complete an **Assess Only**
assessment, and DoD SWP integration guidance expects that evidence to be
continuous — regenerated as the software is built, not assembled once at the
end. SecureTrace operationalizes that: the builder turns *the current state of
a repository worktree* into the four deliverables plus a verifiable evidence
manifest.

Formal input: a repository root `repo` (a directory, git worktree or not).
Formal output: a bundle directory `outdir` containing exactly
`SSP.md`, `SAP.md`, `SAR.md`, `POAM.md`, `manifest.json`, and byte copies of
the evidence corpus under `evidence/<path>` (path = repo-relative POSIX path).

Contract (guaranteed):

- **C1 (determinism):** two runs over the *same tree* (same file bytes, same
  git HEAD) produce byte-identical outputs — every file in the bundle.
- **C2 (SAR invariant):** every control cited in the SAR maps to at least one
  evidence file; asserted structurally on the catalog and behaviorally in tests.
- **C3 (offline):** zero network access — the core reads local files and runs
  one local, offline `git rev-parse` (or degrades to `"no-git"`).
- **C4 (repo-agnostic):** works on any repository that carries (some of) the
  evidence files; a missing file is a defined *outcome* (unsatisfied control),
  never a crash.

Precondition: `repo` exists and is a directory (else `FormatError`).
Undefined: none — the behavior on empty/foreign trees is specified (§5.2).
Forbidden: wall-clock reads inside the core (the date lives only in the
caller-supplied bundle directory name), directory walks outside the fixed
evidence set, network I/O, and locale-dependent formatting.

### 2.2 Why this approach

The deliverables are *renderings of state*, so the design separates three
layers: (1) **collect** — a pure snapshot of the worktree; (2) **render** —
pure string functions of the snapshot; (3) **package** — the only I/O beyond
reading, writing the bundle. This separation is what makes C1 provable: if the
snapshot is deterministic and the renderers are pure, the outputs are
byte-identical by construction.

Key choices:

- **Explicit evidence corpus (20 fixed paths — the 19 unique paths the
  catalog cites, plus `README.md` — and the `algorithms/*.md` glob), not a
  recursive walk.** A walk is host/order-dependent and would swallow
  untracked noise; a fixed list makes the corpus a *defined* set. The single
  glob is for algorithm documents because their count legitimately varies per
  repo; it is sorted, so the set stays deterministic.
- **Fixed 11-control catalog** (work records, QC history, design records,
  traceability, supply chain, gates, quality config, license/packaging,
  release pipeline, SBOM). Controls are *defined*, not discovered: the SAR
  cites a known baseline (C2), and the POA&M is simply "catalog minus
  satisfied" plus open backlog items.
- **Checkers reuse the B3 cores** (`backlog_index.is_fresh`,
  `lessons.record.structural_errors`/`index_is_fresh`,
  `algorithms.registry.is_fresh`) instead of re-parsing — no duplicated
  format knowledge (pragmatic-programmer: no duplication).
- **Canonical manifest** (sorted keys, `indent=2`, one trailing LF) hashing
  every corpus file and every rendered document, so any byte change is
  detectable by anyone with the manifest.

Rejected alternatives:

1. *Fetch CI state from the GitHub API.* Loses: violates C3 (zero network),
   is non-deterministic, and would embed credentials/identity in evidence.
   Local re-checks of the same artifacts are strictly better evidence and are
   what "Assess Only" automation calls for.
2. *Embed generation timestamps in the documents.* Loses: breaks C1 outright
   (two runs an hour apart differ). The date belongs in the *bundle directory
   name*, which the caller (CLI/Makefile) supplies — the core stays time-free.
3. *Recursive repo walk as corpus.* Loses: non-determinism on dirty trees,
   unbounded size, and evidence the controls never cite.

### 2.3 Correctness argument

Invariants (checked at each layer):

- **I1 (corpus):** the corpus is `sorted(set(FIXED ∪ glob) ∩ existing regular
  files)` with `(path, sha256, lines)` per entry. Sorting makes iteration
  order total; hashing binds each entry to exact bytes.
- **I2 (catalog):** every `ControlSpec.evidence` is a non-empty tuple
  (enforced at catalog definition; the SAR-invariant test re-asserts it).
- **I3 (purity):** the four renderers read only their `Evidence` argument —
  no file I/O, no clock, no mutable globals — so equal inputs give equal bytes.
- **I4 (satisfaction):** `satisfied = (present == evidence) ∧ checker_ok`,
  where `checker_ok` is vacuously true for `presence`-method controls and is
  the B3-core check (index fresh + structure valid) otherwise.
- **I5 (manifest):** the manifest contains `sha256` of every corpus file and
  of every rendered document; `package()` computes the document hashes from
  the exact strings it writes.

Why the contract holds: **C1** — the only inputs are file bytes, git HEAD,
and module constants; every iteration is over sorted/fixed collections; the
manifest is canonical JSON — so the mapping from tree to bundle bytes is a
function. **C2** — the SAR is rendered from the catalog (I2), and each row's
evidence column lists `spec.evidence`, so every cited control carries ≥ 1
evidence path. **C3** — the import surface is stdlib-only plus the B3 cores;
the only subprocess is `git rev-parse HEAD` (local object database, no
network), with any failure mapping to `"no-git"`. **C4** — absence of a file
merely removes it from the corpus; every downstream branch (state, checker,
POA&M) is defined on the reduced corpus.

### 2.4 Complexity

`collect`: one pass over the corpus — O(T) byte reads for hashing, line
counting O(T/avg-line), plus O(C·E) set lookups for the controls; the
`git rev-parse` call is O(1) work on the object database (bounded, local).
Renderers: each document is O(C·E + S) — a table row per control plus state
summaries; the SSP/SAP/POA&M share that bound. `package`: O(T) copying plus
O(R) rendering/writing plus one O(M) JSON serialization (M = manifest size
≈ O(C·E + T_paths)). Dominant term: O(T) for collect and package — *claimed,
unverified* until the end-to-end run on SecureTrace itself (corpus ≈ 30
files, sub-megabyte; budget < 1 s on a developer laptop, §6.2).

### 2.5 Deviations

none — documented before implementation (B4, doc-first per G1).

<!-- SECTION:PSEUDOCODE -->
## 3. Pseudocode

```
CONSTANTS
  CATALOG_VERSION := 1
  SCHEMA := "securetrace.rmf-bundle/1"
  # 11 specs, fixed order; each (control_id, title, evidence, method, remediation)
  CATALOG :=
    ST-01  Deterministic work records (backlog)        (BACKLOG.md)                      backlog index check
    ST-02  Quality-control / lessons history           (LESSONS_LEARNED.md)              lessons record check
    ST-03  Algorithm / design records                  (algorithms/INDEX.md) + discovered algorithm docs   per-doc index check
    ST-04  Architecture & requirements traceability    (ARCHITECTURE.md, docs/dow-requirements.md)         presence
    SC-01  Pinned, hashed dependency manifests         (requirements.in, requirements-dev.in,
                                                      requirements.txt, requirements-dev.txt)             presence
    SC-02  Secret-scanning policy & hooks              (.gitleaks.toml, hooks/pre-commit, hooks/pre-push) presence
    CI-01  Gate definitions (local + CI)               (Makefile, .github/workflows/ci.yml)               presence
    QA-01  Code quality configuration                  (pyproject.toml, sonar-project.properties)         presence
    REL-01 License & packaging metadata                (LICENSE, pyproject.toml)                         presence
    REL-02 Release pipeline with provenance            (.github/workflows/release.yml)                   presence
    SB-01  Software bill of materials                  (dist/sbom.json)                                presence
  FIXED := the 19 unique repo-relative paths cited above, plus README.md
           (20 fixed paths total)
  OPEN_STATUSES := {"OPEN", "IN PROGRESS"}

collect(repo) -> Evidence
  pre: repo exists and is a directory        # else raise FormatError("…not a directory")
  paths := sorted(set(FIXED) ∪ sorted(glob(repo, "algorithms/*.md")))
  corpus := []
  for p in paths:
    f := repo/p
    if f is a regular file:                 # else: defined absence (C4)
      b := read_bytes(f)
      corpus.append(Entry(p, sha256_hex(b), count_lines(b)))
  backlog := None
  if "BACKLOG.md" ∈ corpus:
    try rows := backlog_index.index_rows(text("BACKLOG.md"))   # structural
    except FormatError: rows := none                            # -> ST-01 unsatisfied, state absent
    if rows: backlog := State(items=[r for r in rows if r.id ~ ^B\d+$],
                              by_status=counts(items, key=status, sorted),
                              open=[r for r in items if r.status ∈ OPEN_STATUSES, sorted by numeric id])
  lessons := None
  if "LESSONS_LEARNED.md" ∈ corpus:
    if structural_errors(text) == [] and index_is_fresh(text):   # the B3 check, condensed
      lessons := State(total=len(entries), by_severity=counts(entries, key=severity, sorted))
  algo_docs := [p for p in corpus if p starts with "algorithms/" and p != "algorithms/INDEX.md"]
  controls := []
  for spec in CATALOG:
    evidence := spec.evidence ∪ algo_docs if spec.id == "ST-03" else spec.evidence
    present := [p for p in evidence if p ∈ corpus.paths]         # preserves evidence order
    ok := (len(present) == len(evidence))
          and (spec.method == "presence" or all(checker(spec, p) for p in evidence − INDEX.md))
    controls.append(Control(spec, evidence, present, ok))
  git_head := run("git", "-C", repo, "rev-parse", "HEAD")        # offline, local DB
           := "no-git" on any failure                             # defined degradation (C3)
  return Evidence(corpus, backlog, lessons,
                  State(total=len(algo_docs), docs=algo_docs), git_head, CATALOG_VERSION)

render_ssp(evidence) / render_sap(evidence) / render_sar(evidence) / render_poam(evidence) -> str
  # pure: build markdown tables/lists from (corpus, state, controls) only (I3)
  # SSP:  overview, process/QC records, control baseline table, supply chain, related docs
  # SAP:  purpose/scope, control selection (catalog + method), assessment method, evidence corpus table
  # SAR:  summary counts, one row per control (catalog order) with evidence + SATISFIED/NOT SATISFIED,
  #       invariant statement, findings pointer
  # POAM: findings = unsatisfied controls in catalog order (finding + static remediation text),
  #       milestones = open backlog items in numeric id order (or "none")

package(evidence, repo, outdir) -> Path
  pre: outdir is creatable
  for e in evidence.corpus:
    write_bytes(outdir/"evidence"/e.path, read_bytes(repo/e.path)) # byte-identical copy
  docs := {n: render_n(evidence) for n in ["SSP", "SAP", "SAR", "POAM"]}
  for n, text in docs: write_text(outdir/f"{n}.md", text)          # LF, one trailing newline
  manifest := canonical_json({schema, catalog_version, generated_by, git_head,
                              corpus:[{path, lines, sha256}], docs:{n: sha256(text)},
                              controls:[{control_id, title, method, evidence, present, satisfied}],
                              state:{backlog, lessons, algorithms} or nulls})
  write_text(outdir/"manifest.json", manifest + "\n")
  return outdir
```

<!-- SECTION:WALKTHROUGH -->
## 4. Walk-through (plain English)

### 4.1 Step-by-step

1. **Collect the corpus.** Start with the fixed list of evidence paths
   (lockfiles, hooks, workflows, skill documents, SBOM, …) and the algorithm
   documents that actually exist under `algorithms/`. Keep the ones that are
   regular files, hash each (SHA-256) and count its lines. The result is a
   sorted list of `path → (sha256, lines)` — nothing else in the repo is ever
   read.
2. **Parse the process state.** If `BACKLOG.md` is in the corpus, ask the B3
   backlog core for its item rows (id, title, status); keep totals per status
   and the items still open. Same idea for `LESSONS_LEARNED.md` (only when
   the record is structurally valid and its index is fresh) and for the
   algorithm documents (their paths become the design-record state). A missing
   or broken file simply yields `None` state — the bundle still builds.
3. **Evaluate the catalog.** For each of the 11 controls, look up which of
   its evidence files are present. If any is missing → not satisfied. If all
   are present and the control has a live checker (backlog index, lessons
   record, per-doc index), run that checker; a stale index or malformed
   document also flips the control to not satisfied.
4. **Render the four documents.** Pure string building over the snapshot:
   SSP (what the system is + control baseline + supply chain), SAP (how the
   assessment is done + the full evidence table), SAR (one row per control
   with its evidence and SATISFIED / NOT SATISFIED), POA&M (the unsatisfied
   controls with their remediation text, plus open backlog items as
   milestones). No file access, no clock.
5. **Package.** Copy the corpus bytes under `evidence/`, write the four
   documents, then write `manifest.json` — canonical JSON hashing every
   corpus file and every document. The directory name (e.g.
   `artifacts/rmf/2026-10-18`) is the caller's choice; the contents never
   mention the date.

### 4.2 Worked example

Input: a worktree with exactly two evidence files — a valid, index-fresh
`BACKLOG.md` (items B1 DONE, B2 OPEN) and an `LICENSE`. Everything else
absent (no `dist/sbom.json`, no `requirements*`, no `algorithms/` directory).

1. Corpus = `[("BACKLOG.md", sha, 25), ("LICENSE", sha, 21)]` (sorted).
2. State: backlog `total=2`, `by_status={DONE:1, OPEN:1}`, `open=[B2]`;
   lessons = `None`; algorithms = `total=0, docs=[]`.
3. Catalog: ST-01 → `BACKLOG.md` present, index fresh → **SATISFIED**.
   ST-03 evidence resolves to `("algorithms/INDEX.md",)` (no docs exist) →
   missing → **NOT SATISFIED**. The other 9 controls all miss at least one
   evidence file → **NOT SATISFIED**.
4. SAR: 11 rows, `satisfied: 1, not satisfied: 10`. POA&M: 10 findings
   (ST-02 … SB-01, catalog order, each with its static remediation line) and
   one milestone (B2 OPEN). SSP shows 2 evidence files and 0 lessons.
5. Bundle: `SSP.md SAP.md SAR.md POAM.md manifest.json evidence/BACKLOG.md
   evidence/LICENSE`. Re-run on the same tree → identical bytes (C1). Delete
   `LICENSE`, re-run → REL-01 flips to NOT SATISFIED and gains a POA&M
   finding; nothing else changes.

<!-- SECTION:IMPLEMENTATION -->
## 5. Implementation notes (entry-level guide)

### 5.1 Data structures

All frozen dataclasses in `securetrace.rmf.deliverables`:

- `EvidenceFile(path: str, sha256: str, lines: int)` — one corpus entry;
  `path` is repo-relative POSIX; `sha256` is lowercase hex; `lines` counts
  physical lines (`b"\n"` count + trailing partial line).
- `ControlSpec(control_id, title, evidence: tuple[str, ...], method,
  remediation)` — the catalog row; `evidence` non-empty (I2).
- `ControlResult(spec, evidence: tuple[str, ...], present: tuple[str, ...],
  satisfied: bool)` — evaluated row; `evidence` includes ST-03's discovered
  docs; `present` preserves `evidence` order.
- `BacklogState(total, by_status: tuple[tuple[str,int],...],
  open_items: tuple[tuple[str,str,str],...])` — `open_items` =
  `(id, title, status)`, numeric-id order.
- `LessonsState(total, by_severity: tuple[tuple[str,int],...])`.
- `AlgorithmsState(total, docs: tuple[str,...])` — repo-relative paths.
- `Evidence(corpus, backlog, lessons, algorithms,
  controls: tuple[ControlResult, ...], git_head: str, catalog_version: int)`
  — the snapshot the renderers consume (the evaluated catalog is part of the
  snapshot; the renderers never re-evaluate).

Sentinels: `git_head = "no-git"` (not `None`) so the manifest is total;
`None` for `backlog`/`lessons` states means "anchor file absent" (the
renderers print a defined placeholder, not an error).

### 5.2 Edge cases and defined behavior

| Case | Defined behavior | Why |
|---|---|---|
| `repo` missing / not a directory | `collect` raises `FormatError` (CLI maps to exit 2) | the precondition; failing fast beats a bundle of all-missing files with no signal |
| empty directory (no evidence at all) | corpus = `[]`; all 11 controls NOT SATISFIED; bundle still writes all 5 files + empty `evidence/` tree | C4 — absence is data; the POA&M then lists every control, which is the honest assessment |
| `BACKLOG.md` present but structurally broken | corpus entry still hashed; backlog state `None`; ST-01 NOT SATISFIED | the file is evidence of *what is there*; its brokenness is the finding |
| `BACKLOG.md` non-UTF-8 | corpus entry hashed (bytes); state parse skipped → `None`; ST-01 NOT SATISFIED | hashing never needs decoding |
| `algorithms/` missing entirely | ST-03 evidence = `("algorithms/INDEX.md",)` only → NOT SATISFIED; `AlgorithmsState(0, ())` | keeps I2 (≥ 1 evidence path) without inventing files |
| algorithm doc with a stale index | doc is in the corpus; ST-03 NOT SATISFIED (checker ran, index not fresh) | same rule as ST-01/ST-02 — consistent checker semantics |
| git worktree vs. plain directory | `git_head` = HEAD sha vs. `"no-git"`; everything else identical | C3 degradation; determinism unaffected |
| outdir already exists | `mkdir(parents=True, exist_ok=True)`; existing files are overwritten | rebuild-in-place is the expected flow (`make rmf-bundle`) |

### 5.3 CLI contract (pinned)

Command layer (`securetrace.cli.run_rmf_build`, wired as
`securetrace rmf build <repo> [--outdir DIR]`):

- **Success** → stdout, exit 0:
  `{outdir}: RMF bundle written ({satisfied} of {total} controls satisfied)`.
- **Repo missing / not a directory** → stderr, exit 2:
  `securetrace: {repo}: repository root is missing or not a directory`
  (the `FormatError` message, one line).
- **Outdir uncreatable** (e.g. path element is a file) → stderr, exit 2:
  `securetrace: cannot create {outdir}: …` (the `OSError`, one line).
- **Default outdir** — when `--outdir` is omitted, the bundle directory is
  `artifacts/rmf/<YYYY-MM-DD>` relative to the *current working directory*
  (`datetime.date.today().isoformat()`). This is the *only* place a date may
  appear in the B4 surface (the §2.1 prohibition stays intact for the core);
  `make rmf-bundle` supplies the same name from `$(shell date +%F)`.
- Bundles under `artifacts/` are derived outputs: gitignored, regenerated on
  demand, never committed (the repo stays the source of truth).

### 5.4 Invariants and how to test them

- **I1** (sorted, unique corpus) — test: corpus paths strictly ascending;
  recompute `sha256`/`lines` independently and compare.
- **I2** (non-empty evidence) — test: iterate `CATALOG`; assert
  `len(spec.evidence) >= 1`; and behaviorally, parse the SAR rows and assert
  every cited control carries ≥ 1 evidence path (the B4 acceptance assertion).
- **I3** (renderer purity) — test: render twice from the same `Evidence`
  value; bytes equal (covered by the determinism test, which also catches
  hidden globals).
- **I4** (satisfaction rule) — test: reduced-repo fixture flips exactly the
  controls whose evidence/checker regressed; nothing else moves.
- **I5** (manifest hashing) — test: manifest `docs` hashes equal the sha256
  of the written files; `corpus` hashes equal the collector's.

### 5.5 Pitfalls and known traps

- **Do not add `datetime` to the core.** The moment a wall-clock read enters
  `collect`/`render`/`package`, C1 dies. The date belongs only to the
  caller-chosen bundle directory name (CLI/Makefile).
- **Do not use `os.walk`/`glob.glob` over the repo root.** The corpus is the
  fixed set plus the one sorted `algorithms/*.md` glob; anything wider is
  host-order noise.
- **Canonical JSON or the manifest lies.** `json.dumps(obj, indent=2,
  sort_keys=True)` + exactly one trailing `"\n"`; ad-hoc key order breaks
  golden tests on any dict insertion change.
- **CRLF input.** The B3 cores normalize line endings before parsing
  (LLT-0011); the collector must read *bytes* for hashing and only decode
  when a state parse needs text — never "fix" newlines in the corpus copy.
- **Subprocess discipline.** Only `git rev-parse HEAD`, with a timeout and a
  `"no-git"` fallback on *any* failure (missing binary, dirty state, bare
  dir). No environment variables, no `--exec-path`, no network flags.
- **E741 / lint.** No single-letter `l` variables in the render loops
  (ruff enforces); the ruff line limit is 100 columns.
- **`filterwarnings = "error"`** in `pyproject.toml`: the module must be
  warning-clean (no deprecated API, no implicit relative imports).

### 5.6 Language notes

Python 3.12, stdlib-only: `dataclasses` (frozen), `hashlib`, `json`,
`pathlib`, `subprocess` (git only). The B3 cores are reused, not re-implemented.
Idiomatic shape: module-level `CATALOG` constant; private checkers
(`_backlog_ok`, `_lessons_ok`, `_algo_doc_ok`) each returning `bool` and
swallowing `FormatError` into `False`; one public function per layer. The
renderers build strings with `"\n".join(rows)` and end with exactly one
trailing newline. If a future language port is wanted, keep the same layering
— the determinism argument (§2.3) is what must survive translation.

<!-- SECTION:TESTS -->
## 6. Test cases and sample data

All sample data synthetic (G11); the mini-repo fixture
(`tests/fixtures/rmf/mini-repo/`) is a hand-built tree — no git, no network.

| # | Name | Input (sample data) | Expected output | Why it matters |
|---|---|---|---|---|
| 1 | happy path (golden) | mini-repo: all 21 corpus files (20 fixed paths + 1 algorithm doc) incl. valid fresh `BACKLOG.md` (B1 DONE, B2 OPEN), valid `LESSONS_LEARNED.md` (1 lesson), `algorithms/INDEX.md` + 1 valid doc, `dist/sbom.json` | 5 bundle files + evidence copies; SSP/SAP/SAR/POAM/manifest byte-equal to goldens; 11/11 SATISFIED; POA&M milestone = B2 | the reference rendering; pins the exact markdown + manifest format |
| 2 | determinism | same tree, `package()` into two outdirs | every file byte-identical across the two trees | acceptance C1 |
| 3 | SAR invariant | `CATALOG` + rendered SAR | every control spec has ≥ 1 evidence path; every SAR row's evidence paths are corpus members | acceptance C2 (the B4 assertion) |
| 4 | missing evidence | mini-repo copy minus `BACKLOG.md`, `requirements.txt`, `dist/sbom.json` | ST-01, SC-01, SB-01 flip to NOT SATISFIED (exactly those three); POA&M gains exactly those findings; other rows unchanged | I4 — satisfaction is local per control |
| 5 | empty repo | fresh empty directory | corpus `[]`; 11/11 NOT SATISFIED; bundle still writes all 5 files | C4 — absence is data, never a crash |
| 6 | missing repo | non-existent path | `collect` raises `FormatError` | precondition; CLI exit 2 |
| 7 | state parsing | fixture `BACKLOG.md` / `LESSONS_LEARNED.md` / `algorithms/` | backlog `total=2`, `open=[B2]`; lessons `total=1`; algorithms `total=1`; `git_head == "no-git"` | the B3-core reuse path + the git degradation |
| 8 | import surface (offline) | AST of `deliverables.py` | all imports in the stdlib + `securetrace.*` whitelist; none of `urllib`/`socket`/`http*`/`requests` | acceptance C3, enforced by inspection |
| 9 | CLI contract | `tests/test_cli.py` (`rmf` section): mini-repo copy, success / missing repo / uncreatable outdir / default outdir / `main` dispatch | exact pinned messages on the right streams, exit codes 0/2 per §5.3; default outdir `artifacts/rmf/<today>` under the working directory | the user-visible contract is test-pinned, not just implemented |

### 6.1 Property tests (optional but preferred)

For *any* input directory D: (a) corpus paths are strictly ascending and
unique; (b) re-rendering from an equal `Evidence` is byte-equal (I3);
(c) manifest `docs`/`corpus` hashes equal independently computed sha256 (I5);
(d) the set of SATISFIED controls is monotone in the corpus (adding files can
only flip controls toward satisfied, never away — checkers never depend on
other files).

### 6.2 Performance acceptance

SecureTrace repo itself (≈ 30 corpus files, sub-megabyte corpus): full
`collect` + 4 renders + `package` < 1 s wall on a developer laptop;
`make gate` (full suite incl. the golden tests) within the existing CI
budget. *Claimed, unverified* until the end-to-end run (B4 WI 5).

<!-- SECTION:REFERENCES -->
## 7. References

- `docs/dow-requirements.md` — B2 requirements reference: DoDI 8510.01
  (Assess Only; SSP/SAP/SAR/POA&M deliverables), DoDI 5000.87 + DoD
  SWP+RMF integration guidance (continuous/cATO-style evidence, DevSecOps),
  NIST SP 800-218 (SSDF), with source URLs and access date.
- DoDI 8510.01 *RMF for DoD Systems* — https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/851001p.pdf
- NIST SP 800-37 *RMF* / SP 800-53 *Controls* / SP 800-218 *SSDF* —
  https://csrc.nist.gov (frameworks behind the control baseline this bundle
  reports against).
- `algorithms/line-index-sync.md` — the index machinery the ST-01/ST-03
  checkers invoke.
- `algorithms/lessons-record.md` — the record machinery the ST-02 checker
  invokes.
- `tests/fixtures/rmf/mini-repo/` + `tests/fixtures/rmf/golden/` — the
  synthetic sample data and expected outputs for §6.
