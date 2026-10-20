# Backlog

<!-- INDEX:BEGIN format=tsv version=1 -->
id	title	status	priority	start_line	end_line
INDEX_BLOCK	-	-	-	3	17
HEADER	-	-	-	19	25
QUEUE	-	-	-	26	33
B1	Workspace bootstrap (venv, repo, skill docs, CI/CD, gates, skeleton)	DONE	Low	34	73
B2	Research DoW RMF + Software Acquisition Pathway into docs/dow-requirements.md	DONE	Low	74	102
B3	Core CLI: backlog/lessons/algorithm tooling as securetrace package API	DONE	Low	103	141
B4	RMF deliverable builder (SSP/SAP/SAR/POA&M evidence bundles from CI state)	DONE	Low	142	182
B5	Release hardening: keyless signing + provenance for release artifacts	DONE	Low	183	219
B6	SonarCloud quality gate: triage findings on vendored scanner config + scripts	DONE	Low	220	258
B7	SonarCloud code-smell remediation in securetrace core (41 findings, 4 files)	IN_PROGRESS	Low	259	294
B8	Workflow-YAML strict-parse gate (duplicate-key detection in pre-commit + CI)	IN_PROGRESS	Low	295	325
CONSTRAINTS	-	-	-	326	334
<!-- INDEX:END -->

<!-- BACKLOG:HEADER -->
## Status

Tracks all SecureTrace work. Order = all High, then Medium, then Low; within a tier in arrival order (G9).

**Queue:** — | **In progress:** B8, B7 | **Done:** B1, B2, B3, B4, B5, B6 | **Updated:** 2026-10-19

<!-- BACKLOG:QUEUE -->
## Queue (execution order)

1. **B8** (High) — workflow-YAML strict-parse gate (duplicate-key detection in pre-commit + CI)
2. **B7** (Medium) — SonarCloud code-smell remediation in securetrace core (41 findings, 4 files)

Done: **B1** (bootstrap), **B2** (DoW research), **B3** (core CLI), **B4** (RMF deliverable builder), **B5** (release hardening), **B6** (SonarCloud triage) — see their closeouts.

<!-- BACKLOG:ITEM:B1 -->
## B1. Workspace bootstrap (venv, repo, skill docs, CI/CD, gates, skeleton) — **DONE**

- **Source:** user
- **Requested:** 2026-10-18
- **Priority:** High
- **Request (verbatim):** "using @DevSecOps, @Pragmatic Programmer, @Learned Lesson Tracker, @Algorithm Records Keeper, @Backlog Manager, configure my workspace to start working on a project titled 'SecureTrace'… set up a project-global venv at .venv in the root of the workspace… Use the attached GitHub token to create a new public repository called SecureTrace… Configure all skill required documents. Configure CI/CD pipeline. add local pre-commit checks for all document configuration/staleness as appropriate per skill… MIT license… create a skeleton directory structure… Retrieve current software lifecycle requirements from the appropriate DoW websites. include research into THE SOFTWARE ACQUISITION PATHWAY"
- **Problem / evidence:** empty workspace; no gates, no repo, no skill-managed documents; work cannot start with defensible quality gates.
- **Chosen approach:** canonical pragmatic-programmer layout (Makefile, hooks/, tests mirror src), DevSecOps gates (pre-commit: format/lint/docs/secret-scan/changed-tests; pre-push: full suite; commit-msg: Conventional Commits), GitHub Actions pinned by SHA, vendored skill scripts under `scripts/` so CI and hooks do not depend on machine-local skill paths.
- **Work items (in order):**
  1. This backlog entry (done with this file)
  2. `.venv` + pinned deps (ruff, pytest, pip-tools, pip-audit, cyclonedx-bom, build) with hashed lockfiles
  3. Skill documents: BACKLOG.md, LESSONS_LEARNED.md, `algorithms/INDEX.md`
  4. Skeleton package `src/securetrace/` + 1:1 smoke tests
  5. Git hooks (`hooks/`, `core.hooksPath`) + `make gate`
  6. CI workflow (quality + security jobs) + dependabot + release workflow
  7. README, ARCHITECTURE.md, `docs/dow-requirements.md` (from B2 research)
  8. First commit, push to new public `mirph-glitch42/SecureTrace`, CI green
  9. Gate proof (local block + CI red on throwaway branch) + branch protection
  10. Closeout with evidence
- **Blast radius:** the whole workspace (it is empty); nothing must leak (no tokens, no PII) — gitleaks + review.
- **Acceptance criteria:**
  - `make gate` passes locally with all five gate stages green
  - public repo `mirph-glitch42/SecureTrace` exists; `main` pushed; first CI run green
  - pre-commit demonstrably blocks (a) a lint/format/doc-staleness failure and (b) a secret; CI demonstrably red then restored green on a throwaway branch
  - branch protection: required `quality` + `security` checks, 1 approval, no force-push
  - BACKLOG/LESSONS/INDEX documents pass their `--check` scripts
- **Ordering:** first — everything else depends on the gates and the repo.
- **Progress:**
  - 2026-10-18 — status → IN PROGRESS; WI 2, 4 done (venv, skeleton, tests incl. skill-script roundtrip tests)
  - 2026-10-18 — WI 3, 5, 6, 7, 8 done (skill docs, hooks + `make gate`, CI/CD + dependabot, README/ARCHITECTURE, repo created, main pushed, CI green)
  - 2026-10-18 — WI 9–10: CI red drill (run 39120001804 red on throwaway branch, restored green), local gate proofs a/b/c, branch protection set; status → DONE
- **Closeout (2026-10-18, DONE):**
  - **Version:** none (no algorithm work, no releases).
  - **Commits:** `f7904a0` (bootstrap: gates, hooks, CI, skeleton, docs), `c2961e1` (CI venv + full-history checkout + setuptools pin), `307c419` (gitleaks config was a zero-rule no-op; vendored official v8.30.1 defaults + path-scoped allowlist), `3881a89` (pip-audit flag fix).
  - **CI:** `quality` + `security` green on main — runs 39117820614, 39120374470. Red drill: run 39120001804 failed **as expected** on throwaway branch `gateproof/ci-red-drill` (B011 `assert False` caught by quality; pre-fix pip-audit flag caught by security); PR #5 closed unmerged, remote branch deleted.
  - **Local gate proofs (each blocked, HEAD unchanged):** (a) stale BACKLOG index → blocked at docs-check ("index STALE"); (b) unused `import os` → blocked at ruff (F401); (c) staged PEM private key → blocked by gitleaks (rule `private-key`) after the LLT-0004 fix; PEM fixture under `tests/` correctly allowed by path allowlist.
  - **Acceptance:** `make gate` green (18 tests); public repo `mirph-glitch42/SecureTrace` with main pushed and CI green; pre-commit/pre-push/commit-msg hooks committed and proven; branch protection on main: required checks `quality` + `security` (strict/branch-up-to-date), 1 approving review, force-push and deletions disabled (verified via API GET); BACKLOG/LESSONS/INDEX `--check` green.
  - **Lessons:** LLT-0001…LLT-0006 recorded, incl. high-severity LLT-0004 (gitleaks no-op config).

<!-- BACKLOG:ITEM:B2 -->
## B2. Research DoW RMF + Software Acquisition Pathway into docs/dow-requirements.md — **DONE**

- **Source:** user
- **Requested:** 2026-10-18
- **Priority:** High
- **Request (verbatim):** "Retrieve current software lifecycle requirements from the appropriate DoW websites. include research into THE SOFTWARE ACQUISITION PATHWAY"
- **Problem / evidence:** SecureTrace's value proposition (RMF package deliverables built as an agent builds software) must be grounded in current DoD/DoW policy (DoDI 8510.01 RMF, DoDI 5000.87 SWP, NIST SSDF) so B3/B4 build the right artifacts.
- **Chosen approach:** single authoritative `docs/dow-requirements.md` with dated source URLs (DoDI 8510.01, DoDI 5000.87, DoD SWP+RMF integration guidance, cATO/Assess-Only constructs, DISA KS, 32 CFR 111, NIST SP 800-37/800-218), a "what SecureTrace must produce" mapping table, and an access date.
- **Work items (in order):**
  1. This backlog entry
  2. Verify current policy text/URLs (web research, done 2026-10-18 — findings captured in handoff notes)
  3. Write `docs/dow-requirements.md` (requirements, SWP planning/execution phases, Assess-Only evidence bundle, source table)
  4. Cross-link from ARCHITECTURE.md + README
  5. Closeout with evidence
- **Blast radius:** `docs/` only (new file) + one line each in README/ARCHITECTURE.
- **Acceptance criteria:**
  - `docs/dow-requirements.md` exists, cites ≥ 6 primary sources with URLs + access date, and contains a SecureTrace deliverable mapping table
  - every cited URL was retrieved successfully on the access date
- **Ordering:** after B1's repo/gates exist so the doc lands through the pipeline; before B4 (which builds what it specifies). B3 independent.
- **Progress:**
  - 2026-10-18 — research pass complete (findings in session handoff; sources: DoDI 8510.01, DoDI 5000.87, DoD SWP+RMF integration guidance, DoW CTO SE-SWP paper Jan 2026, DISA RMF KS, 32 CFR 111, NIST SSDF)
  - 2026-10-18 — `docs/dow-requirements.md` written, cross-linked (WI 2–5 done); status → DONE
- **Closeout (2026-10-18, DONE):**
  - **Version:** none (documentation deliverable).
  - **Commits:** `f7904a0` (initial landing of `docs/dow-requirements.md`).
  - **CI:** green on main — runs 39117820614, 39120374470 (doc lands through the pipeline).
  - **Acceptance:** `docs/dow-requirements.md` cites 8 primary sources (≥ 6 required) with URLs + access date 2026-10-18: DoDI 8510.01 (RMF, incl. the **Assess Only** construct — SecureTrace's core design input), DoDI 5000.87 (Software Acquisition Pathway: application vs embedded, DA decision-memorandum, semi-annual reporting), DoD SWP+RMF integration guidance (≤6-month increments, cATO, Planning/Execution phases, reciprocity), DoW CTO SE-SWP paper (Jan 2026 — current practice), DAU SWP portal, RMF KS (`rmfks.osd.mil`), NIST SP 800-218 (SSDF), 32 CFR 111 (NSS); "What SecureTrace must produce" mapping table ties each requirement to B1/B3/B4/B5; cross-linked from README.md and ARCHITECTURE.md.

<!-- BACKLOG:ITEM:B3 -->
## B3. Core CLI: backlog/lessons/algorithm tooling as securetrace package API — **DONE**

- **Source:** agent (proposed — flagged to user per G8)
- **Requested:** 2026-10-18
- **Priority:** Medium
- **Request (verbatim):** proposal — "migrate the vendored skill scripts (backlog_index.py, manage_lessons.py, algorithm_index.py) into a typed `securetrace` package API + `securetrace` console entry point with subcommands (backlog check/sync, lessons add/check, algorithms check), preserving the exact index formats so existing hooks and CI keep working"
- **Problem / evidence:** the three gate scripts live in `scripts/` and are invoked ad hoc; users of SecureTrace (agents and humans) need one importable, testable CLI instead of copy-pasted scripts.
- **Chosen approach:** keep `scripts/` as thin entry points (or reimplement the core in the package and keep the scripts as wrappers) so existing Makefile/hooks/CI are untouched; TDD per subcommand; index formats are frozen by the existing roundtrip tests.
- **Work items (in order):**
  1. This backlog entry
  2. Design doc cycle via `@algorithm-records-keeper` where non-trivial (parsing/indexing are simple — likely a short design note suffices)
  3. Tests RED for `securetrace.backlog`, `securetrace.lessons`, `securetrace.algorithms`
  4. Implementation GREEN; `securetrace` console script gains subcommands
  5. `make gate` + CI green; update ARCHITECTURE.md module map
  6. Closeout with evidence
- **Blast radius:** `src/securetrace/{backlog,lessons,algorithms}`, `tests/`, console entry; `scripts/` behavior must not change.
- **Acceptance criteria:**
  - `securetrace backlog check|sync <file>`, `securetrace lessons …`, `securetrace algorithms …` subcommands exist and pass tests
  - existing `make docs-check` continues to pass unchanged
  - new public functions 100% docstring + type-annotated; `ruff`/`pytest` green
- **Ordering:** after B1 (needs gates); independent of B2; B4 builds on it.
- **Progress:**
  - 2026-10-18: started. Ex-post-facto declared (before writing the docs) for two algorithms, pinned to `ad0fc9f`: `line-index-sync` (`scripts/backlog_index.py:L51-L237`, `scripts/algorithm_index.py:L38-L150`, shared delta core) and `lessons-record` (`scripts/manage_lessons.py:L81-L674`) — documentation before code, per @algorithm-records-keeper.
  - 2026-10-18: design fixed — core logic moves into typed package APIs (`securetrace.{backlog,lessons,algorithms}`); `scripts/*.py` become thin wrappers preserving the exact CLI surface, exit codes (0/1/2), and stdout messages; `securetrace` CLI gains `backlog {check,sync}`, `lessons {init,add,sync,check,next-id}`, `algorithms {check,sync}`. TDD: package tests RED first, then GREEN.
  - 2026-10-18 — WI 2 done: two algorithm records backfilled with the *verified pinned* behavior (quirks documented, not fixed — skill anti-abuse rule): `algorithms/line-index-sync.md` (DEV(7) bulleted-priority quirk + DEV(8) final-line scan-window off-by-one) and `algorithms/lessons-record.md` (L13c: malformed Supersedes fires both guards, in order); both registered in `algorithms/INDEX.md` (v0.1.0, `backfilled`, pinned to `ad0fc9f`); LLT-0009…LLT-0012 recorded from the verification.
  - 2026-10-18 — WI 3–4 done: GREEN — typed package core + `securetrace` subcommands implemented; `scripts/{backlog_index,manage_lessons,algorithm_index}.py` are now thin wrappers over `securetrace.cli` (exact CLI surface, messages, exit codes preserved); 131 tests pass; `make gate` ✓.
  - 2026-10-18 — WI 5: ARCHITECTURE.md module map updated; work commits `c3a3f17`…`63c64d3` pushed; on `63c64d3` `quality` + `security` = success and `SonarCloud Code Analysis` = success after triaging 2 new `S8707` findings (see Closeout); status → DONE
- **Closeout (2026-10-18, DONE):**
  - **Version:** none (no release). The two algorithm docs are v0.1.0 **backfills** pinned to `ad0fc9f` (status `backfilled`, per @algorithm-records-keeper); no new algorithm version was assigned.
  - **Commits:** `c3a3f17` `docs(algorithms)` backfill of `line-index-sync` + `lessons-record` (quirks verified against the pinned scripts, documented, not fixed); `2a0e981` `docs(lessons)` LLT-0009…LLT-0012; `971f4ee` `test(cli)` behavioral tests (25 backlog tests incl. the new DEV(8) pin, 13c double-guard pin, CLI surface); `c030082` `feat(cli)` package core + `securetrace` subcommands + thin `scripts/` wrappers; `63c64d3` `docs(architecture)` module map. (Closeout lands in `docs(backlog): close B3`.)
  - **CI (workflow run 39196887061 on `63c64d3`):** `quality` (check 117881474317) + `security` (check 117881474086) = success; `SonarCloud Code Analysis` (check 117881569725) = success **after triage** — the analysis initially failed on 2 new MAJOR `pythonsecurity:S8707` (`src/securetrace/cli.py:56,71`); both transitioned to `wontfix` with justification via `POST /api/issues/do_transition` (LLT-0008 call pattern; same class as the 4 B6 findings: local CLI tools whose caller already has full filesystem access). Project state: 25 open issues, all code smells, **0 open vulnerabilities**.
  - **Acceptance (before→after):**
    - Subcommands: none → `securetrace backlog {check,sync}`, `securetrace lessons {init,add,sync,check,next-id}`, `securetrace algorithms {check,sync}`; every surface (messages, exit codes 0/1/2) covered by `tests/test_cli.py`.
    - Tests: 18 (at B6 closeout) → **131 passed**; `ruff format`/`ruff check` clean; `make gate` ✓ (format, lint, docs, compileall, test).
    - `make docs-check` unchanged and green: BACKLOG.md index OK (10 entries), LESSONS_LEARNED.md valid (12 lessons), both algorithm docs' indexes OK (8 entries each).
    - Frozen `scripts/` surface preserved: `tests/scripts/test_skill_scripts.py` roundtrips still pass; quirks DEV(7)/DEV(8) and L13c encoded in tests + algorithm docs + LLT-0009/LLT-0012 (documented, not fixed — deferred to a doc-first change with its own backlog item).
  - **Lessons:** LLT-0009 (high), LLT-0010 (medium), LLT-0011 (low), LLT-0012 (medium) recorded.

<!-- BACKLOG:ITEM:B4 -->
## B4. RMF deliverable builder (SSP/SAP/SAR/POA&M evidence bundles from CI state) — **DONE**

- **Source:** agent (proposed — flagged to user per G8)
- **Requested:** 2026-10-18
- **Priority:** Medium
- **Request (verbatim):** proposal — "build the 'Assess Only' RMF evidence bundle incrementally from CI state (gate results, dependency audits, SBOM, algorithm records, lessons) and emit SSP/SAP/SAR/POA&M scaffolds per docs/dow-requirements.md"
- **Problem / evidence:** DoD RMF requires SSP/SAP/SAR/POA&M; the SWP guidance expects continuous (Assess Only / cATO-style) evidence. Hand-writing these per release is exactly what SecureTrace automates.
- **Chosen approach:** `securetrace rmf` subpackage: collect artifacts (SBOM, audit reports, gate logs, algorithm registry, lessons) into a dated evidence bundle; render the four deliverables from templates; B2's mapping table drives which evidence feeds which section.
- **Work items (in order):**
  1. This backlog entry
  2. Doc cycle (design + algorithm records where non-trivial)
  3. Evidence collector (deterministic, stdlib-only) with tests RED→GREEN
  4. SSP/SAP/SAR/POA&M renderers with golden-file tests
  5. End-to-end: run on SecureTrace itself, bundle lands in `artifacts/rmf/<date>/` (gitignored or LFS-decided)
  6. Closeout with evidence
- **Blast radius:** new `src/securetrace/rmf/` + `tests/rmf/` + one Makefile target; no changes to existing modules.
- **Acceptance criteria:**
  - `make rmf-bundle` (or `securetrace rmf build`) produces the four deliverables + evidence manifest with zero network access
  - deterministic: two runs on the same tree produce byte-identical outputs
  - every control cited in the SAR maps to at least one evidence file (asserted in tests)
- **Ordering:** after B2 (spec) and B3 (tooling); before B5 (release should ship bundles).
- **Progress:**
  - 2026-10-18 — status → IN PROGRESS (accepted via "complete queue items"); design fixed: `securetrace.rmf.deliverables` with a fixed 11-control catalog (ST/SC/CI/QA/REL/SB), an explicit evidence corpus (no directory walks), checkers reusing the B3 cores (`backlog_index`, `lessons.record`, `algorithms.registry`), pure SSP/SAP/SAR/POA&M renderers, canonical manifest.json; `package()` is time-free — the date lives only in the caller-supplied bundle directory name (determinism acceptance)
  - 2026-10-18 — WI 2 done: spec of record `algorithms/rmf-evidence-bundle.md` v0.1.0 + registry row in `algorithms/INDEX.md`; WI 3–4 started: core collector + 4 renderers with 12 tests in `tests/rmf/test_deliverables.py` (ST-03 failing — `_algo_doc_paths` wrongly counted `algorithms/INDEX.md`)
  - 2026-10-19 — WI 3–4 done: ST-03 fixed (registry excluded from per-doc checks); goldens generated from an out-of-repo fixture copy (`git_head: "no-git"`, LLT-0013); spec v0.2.0 (new §5.3 CLI contract, renumbered §5.4–5.6, test case 9); CLI `run_rmf_build` + guarded `rmf` dispatch (LLT-0014 regression) + `rmf-bundle` Makefile target + `artifacts/` gitignore; 5 new CLI tests; 146 tests green, `make gate` green
  - 2026-10-19 — WI 5 done: E2E on SecureTrace itself — `make sbom` + `make rmf-bundle` → `artifacts/rmf/2026-10-19/`, **11/11 controls SATISFIED**, 23-file corpus, real git HEAD; SAR/manifest sanity-checked
  - 2026-10-19 — work commit `cbcef42` pushed; CI run 39219696994 RED (quality job: 6 golden-dependent test failures)
  - 2026-10-19 — root cause: fixture `tests/fixtures/rmf/mini-repo/dist/sbom.json` was never committed — the repo-level `dist/` gitignore rule shadowed the fixture's nested `dist/` (present on local disk, absent on CI → corpus 20 vs 21); fixed with `.gitignore` negation + committing the file (LLT-0015); `make gate` green (146 tests)
  - 2026-10-19 — fix commit `0541d2f` pushed; CI run 39224391744: `quality` + `security` = success; `SonarCloud Code Analysis` initially failed on 7 new vulnerabilities (6× S8707 + 1× S8705 in `rmf/deliverables.py`, local-CLI class per LLT-0008) → all 7 triaged `wontfix` with justification; all three checks = **success**; status → DONE
- **Closeout (2026-10-19, DONE):**
  - **Version:** none (new `securetrace.rmf` subpackage; spec of record `algorithms/rmf-evidence-bundle.md` v0.2.0, registry state `implemented`).
  - **Commits:** `cbcef42` (B4: spec v0.1.0→v0.2.0, `src/securetrace/rmf/deliverables.py` core, `securetrace rmf build` CLI, `rmf-bundle` Makefile target, 21-file fixture + 5 goldens, 12 core + 5 CLI tests), `0541d2f` (fixture `dist/sbom.json` hidden by `dist/` gitignore — negation rules + commit), `ec92ac5` (LLT-0013..0016).
  - **CI:** run 39224391744 on `0541d2f` — `quality` + `security` = success; external `SonarCloud Code Analysis` = **success** after triaging 7 new vulnerabilities to `wontfix` with justification (6× `pythonsecurity:S8707` in `collect_evidence()`/`package()`, 1× `pythonsecurity:S8705` on the fixed-list `git rev-parse HEAD` call — local-CLI class, LLT-0008 precedent). First red: run 39219696994 — 6 golden-dependent failures, root cause and fix above.
  - **Acceptance (before→after):**
    - Test suite: 131 → **146** (−2 old smoke, +12 core `tests/rmf/`, +5 CLI `rmf` section); `make gate` green locally (format-check / lint / docs-check / build / test).
    - `securetrace rmf build .` and `make rmf-bundle` run with zero network access on SecureTrace itself: `artifacts/rmf/2026-10-19/` with **11/11 controls SATISFIED**, 23-file corpus, real git HEAD; SSP/SAP/SAR/POA&M + canonical `manifest.json`.
    - Determinism: two runs on the same tree are byte-identical (golden + determinism tests); SAR invariant — every control maps to ≥1 corpus file — asserted in tests.
    - CLI contract pinned by tests: success → `{outdir}: RMF bundle written ({n} of {m} controls satisfied)` exit 0; missing repo / uncreatable outdir → `securetrace: {msg}` exit 2; default outdir `artifacts/rmf/<YYYY-MM-DD>` (date only in CLI/Makefile — core stays clock-free).
  - **Lessons:** LLT-0013 (golden HEAD baking), LLT-0014 (unguarded argparse sub-command attribute), LLT-0015 (`dist/` gitignore shadowed a fixture — the CI root cause), LLT-0016 (zsh glob + strict-JSON polling loops).

<!-- BACKLOG:ITEM:B5 -->
## B5. Release hardening: keyless signing + provenance for release artifacts — **DONE**

- **Source:** agent (proposed — flagged to user per G8)
- **Requested:** 2026-10-18
- **Priority:** Low
- **Request (verbatim):** proposal — "add Sigstore cosign keyless signing + SBOM/provenance attestations to release.yml so published wheels/sdists carry verifiable provenance (DevSecOps dependency-security guidance)"
- **Problem / evidence:** unsigned PyPI artifacts are unauditable; DoW-facing users will expect supply-chain evidence.
- **Chosen approach:** cosign keyless (OIDC via GitHub Actions), `cosign sign-blob` on wheel/sdist, `slsa-provenance` or `sigstore` provenance attestation; verify step in CI.
- **Work items (in order):**
  1. This backlog entry
  2. Design note + pin cosign action SHAs
  3. Wire into release.yml (sign → attest → verify)
  4. Tag a test release, verify signatures with `cosign verify`
  5. Closeout with evidence
- **Blast radius:** `.github/workflows/release.yml` only.
- **Acceptance criteria:** published artifacts have verifiable keyless signatures; verify step fails on tampered artifact (test on throwaway branch).
- **Ordering:** last — after B4 so releases ship RMF bundles; independent of B3.
- **Progress:**
  - 2026-10-19 — status → IN PROGRESS (B4 closed same day); design per Sigstore official CI quickstart: `cosign sign-blob` (keyless, Fulcio OIDC via `sigstore/cosign-installer` pinned by SHA, `COSIGN_VERSION` pinned) on wheel+sdist, `gh attestation` (GitHub-native SLSA v1 provenance) for both artifacts, identity-pinned `cosign verify-blob` + `gh attestation verify` steps BEFORE release creation (fail-fast: a tampered artifact can never be published); consumers verify with stock cosign/gh
  - 2026-10-19 — design pivot (run 39234156533 went RED: current `gh` CLI has **no create subcommand** for `gh attestation` — only download/trusted-root/verify). New provenance path per 2026 GitHub docs: `actions/attest` (SHA-pinned v4, SLSA v1 provenance mode, multi-subject) + repo-level **immutable releases** (`PUT /repos/.../immutable-releases`): tag+assets locked, auto signed release attestation at creation, consumer recipe `gh release verify` / `gh release verify-asset`. cosign keyless signing + identity-pinned verify unchanged. ARCHITECTURE.md §5 updated as design of record.
  - 2026-10-19 — root cause of the 0-job fallback-name failures found and fixed: duplicate `attestations:` key in `permissions` (GitHub's yaml.v3 parser hard-fails on duplicate mapping keys; Ruby Psych / PyYAML silently tolerate — local green, GitHub red). Proven by ~13 controlled temp-workflow tests + a Ruby duplicate-key walker. Fix `e116bd2`: single `attestations: write`, release.yml pure ASCII, ARCHITECTURE.md §5 synced, temp diagnostics removed; gate green (146 tests); workflow re-registered as `Release` (active); re-tagged `v0.1.0` -> `e116bd2`; CI on `e116bd2` green.
  - 2026-10-19 — run 39245874727: all 16 steps executed, release + 6 assets published, but step 16 `gh release verify` failed `no attestations for tag v0.1.0`. Root cause: `gh release verify` looks up the **release attestation** (subject = tag ref digest `sha1:<tag-object-sha>`, predicate `release`, initiator `github`) which GitHub creates **asynchronously** after publish — the verify ran ~0.4 s after `gh release create`. Attestation confirmed present minutes later (id 57367814, `GET /repos/.../attestations/sha1:e29193ea...`). Fixed: step 16 now retries 10 x 30 s; step 15 idempotent (`gh release delete` before `create`). ARCHITECTURE.md §5 documents both attestation classes + digest-keyed list endpoints.
  - 2026-10-19 — re-tag `v0.1.0` → `1f89f0c` blocked by GitHub: deleting the old tag required deleting release 417220556 first (tag+release coupled), but then re-creating the exact name `v0.1.0` was refused (GH013 `Cannot create ref due to creations being restricted`; REST + GraphQL ruleset lists empty at repo level, no orgs, no user-level endpoint; new tag names — `probe-tag-check`, `v0.2.9-probe` — created and deleted fine; ~8 attempts over ~10 min all failed). Matches a GitHub community report of the identical invisible block. Decision: ship the identical hardening as **v0.1.1**; version bump `0.1.0 → 0.1.1` (`pyproject.toml` + `__version__` + regenerated RMF golden `manifest.json` `generated_by`; consumer recipe in ARCHITECTURE.md §5 switched to `<tag>` placeholders so it never pins a version). Commit `8db543c`; CI run 39261482050 green.
  - 2026-10-19 — **Release run 39261660707** (tag `v0.1.1` → `8db543c`): all 16 steps **success**, including the first real pass of the idempotent publish + retry-verify design (step 16 passed on attempt 1/10 — `✓ Release v0.1.1 verified!` + `verify-asset` for wheel and sdist). Release 417335625 published with 6 assets: wheel `sha256:f76b43…` (34,307 B), sdist `sha256:361a3c…` (172,244 B), `sbom.json`, 2× `*.sigstore.json`, `attestation-bundle.json`. Attestations confirmed via digest-keyed API: release attestation on tag object (initiator `github`) + artifact attestations on the wheel digest.
  - 2026-10-19 — tamper red-drill (acceptance: verify fails on tampered artifact): throwaway branch `bionic/b5-tamper-drill` @ `939600e` inserted a byte-flip of both `dist/` artifacts AFTER signing+attestation, BEFORE verify; tag `v0.0.0-drill` → run **39259302690** = `completed|failure`, failing step exactly `Verify signatures (identity-pinned…)` — cosign: `matching bundle to payload: bundle="e18ab5…" payload="c34cc7…"`; all publish steps skipped; **0 releases** existed after the run. Drill tag + branch deleted (remote + local).
  - 2026-10-19 — status → DONE (closeout below).
- **Closeout (2026-10-19, DONE):**
  - **Version:** package `0.1.0 → 0.1.1` (the `v0.1.0` tag name is blocked for re-creation by an invisible GitHub-side rule — see progress above; `v0.1.1` ships the identical code + hardening and keeps artifact names consistent with the tag).
  - **Commits:** `e116bd2` (duplicate-`attestations:`-key parse-failure fix), `1f89f0c` (retry-verify + idempotent delete-then-create publish), `8db543c` (version bump 0.1.0→0.1.1, golden `generated_by` regen, `<tag>` consumer recipe).
  - **CI / runs:** CI run 39261482050 on `8db543c` — `quality` + `security` + `SonarCloud` = success. Release run 39261660707 (tag `v0.1.1`) — 16/16 steps success. Red-drill run 39259302690 (tag `v0.0.0-drill`) — RED at `Verify signatures` exactly as designed, no release created. Prior red: run 39245874727 (async release-attestation race at step 16 — fixed by `1f89f0c`).
  - **Acceptance (before→after):**
    - Before: unsigned wheel/sdist, no provenance, mutable release, no consumer verification path, no tamper detection.
    - After: every published artifact carries (a) a Sigstore **keyless** signature bundle (Fulcio OIDC; `cosign verify-blob` green with identity pinned to workflow file + tag), (b) **SLSA v1 provenance** attestation (`actions/attest@1e69f48…`; `gh attestation verify --signer-workflow …/release.yml` green), (c) a **GitHub release attestation** (initiator `github`, verified in-pipeline by `gh release verify` + `gh release verify-asset`, retry-tolerant to the documented async gap); repo-level **immutable releases**; idempotent publish (rerun/re-tag safe); consumer recipe + both attestation classes documented in ARCHITECTURE.md §5.
    - Tamper drill: a single byte flipped after signing+attestation → run RED at `Verify signatures` (cosign bundle-vs-payload digest mismatch), zero releases published — acceptance criterion met.
  - **Lessons:** LLT-0017…LLT-0027 (duplicate YAML keys vs GitHub parser; workflow parse-failure signature; `gh attestation create` absent; `--signer-repo` shadowing; action input names at the pinned SHA; `--verify-tag`; ASCII-only workflow YAML; async release-attestation race; digest-keyed attestations API; invisible tag-name re-creation block; golden manifest embeds package version).

<!-- BACKLOG:ITEM:B6 -->
## B6. SonarCloud quality gate: triage findings on vendored scanner config + scripts — **DONE**

- **Source:** agent (proposed — flagged to user per G8)
- **Requested:** 2026-10-18
- **Priority:** High
- **Request (verbatim):** proposal — "the SonarCloud Code Analysis check (external GitHub App, not part of our workflow) has been failing on main since 307c419: 16 BLOCKER false positives (secrets:S6334) on sample tokens inside the vendored `.gitleaks-defaults.toml`, plus 4 MAJOR pythonsecurity:S8707 findings on the vendored scripts' CLI arguments; triage the findings, add a durable exclusion so the vendored scanner rule definitions are never re-flagged, and record lessons"
- **Problem / evidence:** check run on `4b1646a`: `SonarCloud Code Analysis: failure` — failed condition "Security Rating on New Code (required ≥ A)". 34 open issues: 16× BLOCKER `secrets:S6334` in `.gitleaks-defaults.toml` (sample tokens inside rule definitions — false positives; the file IS the scanner's rule set, same reason gitleaks' own repo allowlists its config path); 4× MAJOR `pythonsecurity:S8707` (backlog_index.py:209,231; algorithm_index.py:122,144 — CLI path arguments of local tools); 14× code smells in vendored scripts (not failing the gate). Contractual CI checks `quality` + `security` remain green.
- **Chosen approach:** transition the 16 FPs to `falsepositive` and the 4 S8707 findings to `won'tfix` via the SonarCloud API with justifying comments (no code changes to the vendored skill scripts — they must stay in sync with the skill); add `sonar-project.properties` excluding `.gitleaks-defaults.toml` so future analyses cannot re-flag the vendored rule definitions; record lessons (red-drill protocol + SonarCloud findings).
- **Work items (in order):**
  1. This backlog entry
  2. Triage all 34 open issues (FP / won'tfix with justification comments; leave code smells open)
  3. Add `sonar-project.properties` (exclusion + provenance comment)
  4. Lessons: LLT-0007 (red-drill protocol, from handoff) + LLT-0008 (SonarCloud flags vendored scanner rule definitions / S8707 on local CLI tools)
  5. Push (triggers SonarCloud re-analysis); confirm check green + `make gate` green
  6. Closeout with evidence
- **Blast radius:** `sonar-project.properties` (new file), `LESSONS_LEARNED.md`, `BACKLOG.md`; SonarCloud issue states (external system); NO changes to `src/` or `scripts/`.
- **Acceptance criteria:**
  - `SonarCloud Code Analysis` check = success on the latest main commit
  - zero open BLOCKER/MAJOR vulnerabilities project-wide (all transitioned with justification)
  - `sonar-project.properties` committed; `.gitleaks-defaults.toml` excluded from analysis
  - `make gate` green locally and `quality` + `security` green in CI
- **Ordering:** before the Dependabot PR merges (each merge pushes to main and triggers re-analysis — triage must be in place first).
- **Progress:**
  - 2026-10-18 — status → IN PROGRESS; all 34 issues triaged and classified
  - 2026-10-18 — WI 2 complete: 20/20 transitions applied via `POST https://sonarcloud.io/api/issues/do_transition` (param `transition`; values `falsepositive`/`wontfix`; each HTTP 200 with justification comment). The earlier 404s were endpoint/param-name misses (`dotransition`/`transitionKey`), not a missing endpoint. Project state after: 14 open issues (all code smells in vendored scripts — left open per triage), **0 open vulnerabilities**.
  - 2026-10-18 — WI 3–4 complete: `sonar-project.properties` added (`sonar.exclusions=.gitleaks-defaults.toml` + provenance comment); LLT-0007 (red-drill protocol) + LLT-0008 (SonarCloud vendored-config FPs, S8707 on local CLIs, limited API subset) recorded; `manage_lessons.py check` green (8 lessons).
  - 2026-10-18 — WI 5–6 complete: work commit `8267c48` pushed; on that commit `SonarCloud Code Analysis` = **success** (check run 117677306462), `quality` + `security` = success (workflow run 39128051807); status → DONE
- **Closeout (2026-10-18, DONE):**
  - **Version:** none (triage/config deliverable; no algorithm doc).
  - **Commits:** `8267c48` `fix(quality): exclude vendored scanner config from SonarCloud analysis` (lands `sonar-project.properties`, LLT-0007/0008, B6 progress).
  - **CI:** workflow run 39128051807 on `8267c48` — `quality` (job 117677232960) + `security` (job 117677233103) = success; external `SonarCloud Code Analysis` check (run 117677306462) = **success** (was failing on every commit since `307c419`).
  - **Acceptance (before→after):**
    - `SonarCloud Code Analysis` check: failure ("Security Rating on New Code required ≥ A", since `307c419`) → **success** on `8267c48`.
    - Open issues: 34 (20 vulnerabilities: 16× BLOCKER `secrets:S6334` in `.gitleaks-defaults.toml` + 4× MAJOR `pythonsecurity:S8707` in `scripts/`) → **14 (0 vulnerabilities)**; all 20 transitioned with justification comments via `POST /api/issues/do_transition` (param `transition`; values `falsepositive`×16, `wontfix`×4; each HTTP 200); the 14 remaining are code smells in vendored scripts, left open per triage decision.
    - `sonar-project.properties` committed at repo root: `sonar.exclusions=.gitleaks-defaults.toml` + provenance comment (prevents re-flagging on future analyses).
    - `make gate` green locally (18 tests) before push; pre-commit gate green on commit.
  - **Notes:** the endpoint 404s in the session handoff were a name miss — the working call is `POST https://sonarcloud.io/api/issues/do_transition` with `issue=<key>`, `transition=falsepositive|wontfix`, `comment=<text>` (recorded in LLT-0008).

<!-- BACKLOG:ITEM:B7 -->
## B7. SonarCloud code-smell remediation in securetrace core (41 findings, 4 files) — **IN PROGRESS**

- **Source:** agent (proposed — flagged to user per G8; approved "go for both" 2026-10-19)
- **Requested:** 2026-10-19
- **Priority:** Medium
- **Request (verbatim):** proposal — "remediate the 41 SonarCloud code smells in `src/securetrace` + `tests` (S6353 regex digit classes, S8786 super-linear regexes, S3776 complex functions, S1192 magic strings, S9409 consecutive appends, S5778 multi-invocation exception tests) with behavior-preserving refactors, each increment gate-green before commit"; user approval (2026-10-19): "go for both"
- **Problem / evidence:** SonarCloud API census (`GET /api/issues/search?projects=mirph-glitch42_SecureTrace&ps=200`, measured 2026-10-19): 84 total issues, **0 open** — but 41 code smells in `src/securetrace` + `tests` are held as `WONTFIX` stopgaps (gate-green triage) instead of fixed: `src/securetrace/lessons/record.py` — S6353×6 (L61, 62, 65, 66) + S8786×2 (L62, 63) + S3776×4 (L155 cc=63, L256 cc=16, L436 cc=16, L468 cc=23); `src/securetrace/rmf/deliverables.py` — S6353×1 (L60) + S1192×5 (L136, 143, 186, 401, 502) + S9409×10 (L445, 465, 469, 477, 487, 507, 531, 550, 566, 581); `src/securetrace/backlog/index.py` — S8786×1 (L57); `tests/lessons/test_record.py` — S5778×12 (L196–278).
- **Chosen approach:** six behavior-preserving increments in dependency order (S6353 → S9409 → S1192 → S8786 → S3776 → S5778), each `make gate`-green before commit (146 tests + `tests/rmf/` goldens pin behavior bit-for-bit); regex rewrites keep the language exactly (ASCII-scoped `\d` via `(?a:...)`; unambiguous linear quantifiers instead of lazy `.*?\s*$`); S3776 decomposes into small helpers preserving exact error-message strings and order (frozen by tests + LLT-0009/0012); S5778 restructures each exception test to exactly one potentially-throwing invocation in the test body.
- **Work items (in order):**
  1. This backlog entry
  2. Increment 1 — S6353: `[0-9]` → ASCII-scoped `\d` (`record.py` ×6, `deliverables.py` ×1); gate + commit
  3. Increment 2 — S9409: `deliverables.py` renderers — consecutive `lines.append` → `extend` / list literals (byte-identical output); gate + commit
  4. Increment 3 — S1192: `deliverables.py` repeated string literals → module constants (identical output); gate + commit
  5. Increment 4 — S8786: `record.py` L62/63 + `index.py` L57 regexes → linear equivalents (same language; suite verifies); gate + commit
  6. Increment 5 — S3776: `record.py` L155/256/436/468 → small helpers (cc ≤ 15), error strings + order preserved; gate + commit
  7. Increment 6 — S5778: `test_record.py` ×12 → one potentially-throwing invocation per test body; gate + commit
  8. Push; SonarCloud re-analysis → the 41 findings resolve to `FIXED`/closed; `SonarCloud Code Analysis` check green
  9. Closeout with evidence (B7 + B8 land in the same final change)
- **Blast radius:** `src/securetrace/{lessons/record.py, rmf/deliverables.py, backlog/index.py}`, `tests/lessons/test_record.py`; observable behavior must stay bit-identical (146 tests + `tests/rmf/` goldens — no golden regeneration); the 9 `pythonsecurity:S8705/S8707` WONTFIX (`cli.py` ×2, `deliverables.py` ×7 — LLT-0008 precedent) and vendored `scripts/*` findings stay untouched.
- **Acceptance criteria:**
  - after the final push + re-analysis, 41/41 B7-scope findings are `FIXED`/closed or absent (re-measured via the SonarCloud issues API)
  - `make gate` green after every increment — 146 tests pass and `tests/rmf/` goldens byte-identical (no golden regeneration)
  - `SonarCloud Code Analysis` check = success on the final `main` commit; 0 open issues project-wide
  - LLT-0009/LLT-0012 pinned quirks still pass (documented, not fixed — behavior unchanged by construction)
- **Ordering:** after B8 (queue priority: High before Medium; B8's gate change lands first so B7's refactor churn runs under it).
- **Progress:**
  - 2026-10-19 — created (G1); status OPEN; queued behind B8 (G9)
  - 2026-10-19 — status → IN PROGRESS (G2: flip rides with first work); B8 stays IN PROGRESS until the joint closeout
  - 2026-10-19 — WI 2 (increment 1, S6353): `[0-9]` → ASCII-scoped `(?a:\d)` — `record.py` ×6 (ENTRY_MARKER_RE, HEADING_RE, ID_RE, DATE_RE) + `deliverables.py` ×1 (_B_ITEM_RE); the `LLT-[0-9]{4}` error-message literal is a format description, not a regex (left per B7 blast radius); `algorithms/lessons-record.md` cited patterns synced + 0.1.1 (ALRK rule 5) + registry row; `make gate` green (155 tests, goldens byte-identical, no regen)
  - 2026-10-19 — WI 3 (increment 2, S9409 ×10): the 4 RMF renderers (`render_ssp`/`render_sap`/`render_sar`/`render_poam`) rewritten so no two consecutive `lines.append` calls remain — static runs became list literals / `lines.extend([...])`; loop bodies keep one append per iteration; output byte-identical (`tests/rmf/` goldens pass, no regeneration); no doc change (algorithm unchanged — verified `rmf-evidence-bundle.md` cites concepts, not code); `make gate` green (155 tests)
  - 2026-10-19 — WI 4 (increment 3, S1192 ×5): module constants before `CATALOG` — `BACKLOG_DOC` / `LESSONS_DOC` / `PYPROJECT_TOML` / `SEPARATOR_3` / `SEPARATOR_4` — replacing every code occurrence (4+4+3 file-name sites in CATALOG/FIXED/state parsers; 3+3 separator sites across the 5 renderers); human-readable remediation prose in CATALOG left untouched (format description, not code); each literal now appears exactly once; output byte-identical (goldens pass, no regeneration); no doc change (algorithm unchanged); `make gate` green (155 tests)
  - 2026-10-19 — WI 5 (increment 4, S8786 ×2): record.py HEADING_RE/FIELD_RE value groups → linear-time `\S+(?:\s+\S+)*` / `\S*(?:\s+\S+)*`; index.py MARKER_RE → anchored alternation-free KIND_MARKER_RE + ITEM_MARKER_RE + private `_marker_on_line` helper (reserved-kind validation in Python — unknown kinds and bare `ITEM` still ignored); guard order + all error strings unchanged (pinned tests pass); docs synced same change (ALRK rule 5): lessons-record.md → 0.1.2, line-index-sync.md → 0.1.1, registry rows updated; `make gate` green (155 tests)
  - 2026-10-19 — WI 6 (increment 5, S3776 ×4): `parse_entries` → `_check_heading`/`_parse_fields`/`_check_required_fields`/`_check_field_vocabularies`/`_check_optional_fields` (+ `_find_heading`); `check_consistency` → `_check_supersession`/`_check_superseded_have_successor`/`_check_id_order`; `_validate_new_lesson` → `_validate_required`/`_validate_vocabularies`/`_validate_optional_single_line`; `add_lesson` → `_supersede_target`/`_assign_entry_id`; every error string and its emission order byte-identical (pinned tests pass); no doc change (algorithm unchanged — doc cites the public entry points only); `make gate` green (155 tests)
  - 2026-10-19 — WI 7 (increment 6, S5778 ×12): 12 exception tests in `tests/lessons/test_record.py` carried setup constructors (TEMPLATE/BASE/TWO/lesson(...)) inside the `pytest.raises` body beside `add_lesson` — setup objects hoisted to module-level constants (pure constructors, safe at import) so each flagged body is exactly one throwing invocation; unflagged exception tests (single-call bodies) and non-exception tests untouched; no doc change (test-only); `make gate` green (155 tests)

<!-- BACKLOG:ITEM:B8 -->
## B8. Workflow-YAML strict-parse gate (duplicate-key detection in pre-commit + CI) — **IN PROGRESS**

- **Source:** agent (proposed — flagged to user per G8; approved "go for both" 2026-10-19)
- **Requested:** 2026-10-19
- **Priority:** High
- **Request (verbatim):** proposal — "close the parser-divergence gap that broke B5: GitHub's yaml.v3 parser hard-fails on duplicate mapping keys while PyYAML/Ruby Psych silently tolerate them (LLT-0017) — add a strict YAML check for `.github/workflows/*.yml` to the pre-commit gate and the CI quality job, TDD-first, dependency pinned + hashed"; user approval (2026-10-19): "go for both"
- **Problem / evidence:** B5 incident (2026-10-19): duplicate `attestations:` key in `release.yml` `permissions` — every local gate green (no YAML stage), `Release` run 39234156533 produced zero jobs; root-caused via ~13 controlled probe workflows + a Ruby duplicate-key walker (LLT-0017, high). Current pre-commit gate (5 stages: format-check / lint / docs-check / secrets / tests) and the CI quality job have **no** workflow-YAML validation — a duplicate key in `ci.yml` or `release.yml` ships to GitHub and fails only there.
- **Chosen approach:** new checker `scripts/check_workflow_yaml.py` (PyYAML `SafeLoader` subclass that rejects duplicate mapping keys, reporting file + key + 1-based line; exit 0 = clean, 1 = duplicate keys or parse error, 2 = usage error) wired as Makefile `workflow-check` target + pre-commit stage (renumber to 6) + CI quality-job step — one change per the Makefile/hook contract comment; `pyyaml` added to `requirements-dev.in` + `make lock` (hashed pin, DevSecOps); TDD RED first in `tests/scripts/test_workflow_yaml.py`; short algorithm doc (`algorithms/workflow-yaml-strict-parse.md`) before code per @algorithm-records-keeper.
- **Work items (in order):**
  1. This backlog entry
  2. Algorithm doc v0.1.0 + `algorithms/INDEX.md` registry row (status `implemented`) + its index regen
  3. RED: `tests/scripts/test_workflow_yaml.py` — clean file passes; duplicate top-level key fails with key + line; nested duplicate fails; flow-style `{a: 1, a: 2}` fails; malformed YAML → exit 1; missing file → exit 2; default discovery finds and passes both real workflow files
  4. GREEN: `scripts/check_workflow_yaml.py`; `pyyaml` into `requirements-dev.in` + `make lock` + venv install
  5. Wire ONE change: Makefile `workflow-check` target + `gate` + `.PHONY` + help; pre-commit stage 4 (6 stages); ci.yml quality step after docs-check
  6. `make gate` green (146 existing + new tests); local red-proof (staged scratch workflow with a duplicate key blocks, then removed); commit; push; CI green
  7. Closeout with evidence (B7 + B8 land in the same final change)
- **Blast radius:** new `scripts/check_workflow_yaml.py` + `tests/scripts/test_workflow_yaml.py`; `Makefile` (new target, `gate` list, `.PHONY`, help); `hooks/pre-commit` (new stage 4, stages renumber 4→5, 5→6); `.github/workflows/ci.yml` (one new step in `quality`); `requirements-dev.in` / `requirements-dev.txt` (pyyaml pin + hashes); `algorithms/` (new doc + registry row). No changes to `src/securetrace/` or to existing workflow behavior.
- **Acceptance criteria:**
  - a duplicate-key workflow YAML is rejected locally at the new pre-commit stage AND by the CI quality job, reporting file + key + line (local red-proof: staged scratch workflow blocks the hook, then removed; TDD RED evidence in `tests/scripts/`)
  - `make gate` green including the new stage — 146 existing tests still pass + new test file green
  - `pyyaml` pinned with hashes in `requirements-dev.txt` (`pip-compile --generate-hashes`); `dependency-audit` green in CI
  - both current workflow files (`ci.yml`, `release.yml`) pass the new check
- **Ordering:** before B7 (queue priority High > Medium; the gate lands first so B7's churn runs under it).
- **Progress:**
  - 2026-10-19 — created (G1); accepted for execution ("go for both")
  - 2026-10-19 — status → IN PROGRESS (G2: flip rides with first work); WI 2 done: `algorithms/workflow-yaml-strict-parse.md` v0.1.0 (draft) + `algorithms/INDEX.md` registry row + doc index regen
  - 2026-10-19 — WI 3 RED: 9 tests in `tests/scripts/test_workflow_yaml.py` (all failing — checker absent); WI 4 GREEN: `scripts/check_workflow_yaml.py` per spec; `pyyaml==6.0.3` pinned + hashed (`requirements-dev.{in,txt}`); 9/9 pass
  - 2026-10-19 — WI 5: wired in ONE change — Makefile `workflow-check` (gate + .PHONY + help), pre-commit stage 4 (renumbered to 6 stages), CI quality step; doc → v0.2.0 `implemented` + registry row
  - 2026-10-19 — WI 6: `make gate` green (155 tests); local red-proof: probe workflow with duplicate `on:` blocked at stage 4/6 (`duplicate key 'on' at line 2`, make Error 1), then removed and stage green; HEAD clean

<!-- BACKLOG:CONSTRAINTS -->
## Standing constraints

- All changes gate on `make gate` locally and CI (`quality` + `security`) — no bypass, ever.
- No secrets or PII in the repo (gitleaks in pre-commit + CI; the GitHub PAT is never committed or echoed).
- Versions are assigned at completion only (G6) — never planned.
- Agent-proposed items stay flagged (G8) until the user accepts or amends them.
- Dependency changes only via pinned, hashed lockfiles (`pip-compile --generate-hashes`).
- `algorithms/` holds algorithm *documents*; `src/securetrace/algorithms/` holds code — do not mix.
