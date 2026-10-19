# Lessons Learned

Authoritative record of lessons learned during the development of this system:
the situation, the pitfall, and the correct solution for each lesson.
Managed by the `learned-lesson-tracker` skill — do not edit the index block or
the entry markers by hand; use `scripts/manage_lessons.py` (init / add / sync /
check / next-id). The index below is machine-readable (TSV between
`LLT:INDEX:BEGIN`/`LLT:INDEX:END` markers) and lists every entry with its
line range.

<!-- LLT:INDEX:BEGIN -->
id	title	category	severity	status	recorded	start_line	end_line
LLT_INDEX_BLOCK	—	—	—	—	—	11	30
LLT-0001	cyclonedx CLI binary is cyclonedx-py, not cyclonedx-bom	tooling	medium	active	2026-10-18	32	45
LLT-0002	skill scripts must be vendored into the repo for CI and hooks	architecture	medium	active	2026-10-18	46	59
LLT-0003	zsh does not word-split unquoted variables	environment	low	active	2026-10-18	60	73
LLT-0004	gitleaks custom config WITHOUT rules is a no-op scanner (zero rules)	security	high	active	2026-10-18	74	87
LLT-0005	pip --require-hashes fails on clean runners when a transitive dep is unpinned	tooling	medium	active	2026-10-18	88	101
LLT-0006	gitleaks full-history scan needs fetch-depth 0 on CI	tooling	medium	active	2026-10-18	102	115
LLT-0007	Red-drill protocol for proving gates actually catch failures	process	medium	active	2026-10-18	116	129
LLT-0008	SonarCloud mis-flags vendored scanner configs and local CLIs; its API is a limited subset	tooling	high	active	2026-10-18	130	143
LLT-0009	Priority regex silently misses bulleted `- **Priority:** X` lines	tooling	high	active	2026-10-18	144	157
LLT-0010	Lessons-index staleness covers geometry + indexed fields, not body content	testing	medium	active	2026-10-18	158	171
LLT-0011	Universal-newline reads make CRLF handling differ from code appearance	environment	low	active	2026-10-18	172	185
LLT-0012	backlog scan window excludes the final line of a section (off-by-one)	tooling	medium	active	2026-10-18	186	199
LLT-0013	Golden files generated inside the repo bake the real git HEAD into the manifest	testing	medium	active	2026-10-19	200	213
LLT-0014	Unguarded args.<sub>_command access in argparse dispatch crashes sibling subcommands	tooling	high	active	2026-10-19	214	227
LLT-0015	Repo-level 'dist/' gitignore rule silently drops nested test fixture files from the commit	testing	high	active	2026-10-19	228	241
LLT-0016	zsh globbing and strict JSON parsing silently break curl API polling loops	environment	medium	active	2026-10-19	242	255
<!-- LLT:INDEX:END -->

<!-- LLT:ENTRY:LLT-0001 -->
## LLT-0001 — cyclonedx CLI binary is cyclonedx-py, not cyclonedx-bom

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** Wiring SBOM generation into the Makefile and CI for the SecureTrace bootstrap (B1). The PyPI package is named cyclonedx-bom, so the natural guess for the entrypoint was cyclonedx-bom.
- **Pitfall:** Invoking cyclonedx-bom fails with command-not-found; the package installs the binary as cyclonedx-py. A Makefile variable or CI step written from the package name silently breaks SBOM generation.
- **Solution:** Set the Makefile CDX variable to cyclonedx-py and use that name in CI. Add a smoke check (cyclonedx-py --version) to setup-ci so the mismatch is caught at setup time.
- **Supersedes:** —
- **Prevention:** Makefile setup target runs `$(CDX) --version`; CI setup-ci step runs the same
- **References:** requirements-dev.in; Makefile (CDX variable); https://pypi.org/project/cyclonedx-bom/

<!-- LLT:ENTRY:LLT-0002 -->
## LLT-0002 — skill scripts must be vendored into the repo for CI and hooks

- **Recorded:** 2026-10-18
- **Category:** architecture
- **Severity:** medium
- **Status:** active
- **Context:** Configuring SecureTrace gates (B1): pre-commit hooks and GitHub Actions must run the backlog-manager / learned-lesson-tracker / algorithm-records-keeper index scripts, but those scripts live in the machine-local skill directory (~/.lmstudio/skills/...).
- **Pitfall:** A hook or CI job that calls the skill path breaks on every other checkout, on CI runners, and on fresh machines; the gate becomes environment-specific and silently unenforceable.
- **Solution:** Vendor the three scripts into scripts/ (backlog_index.py, manage_lessons.py, algorithm_index.py) with a provenance note in each docstring, and make hooks, Makefile, and CI all reference the vendored copies. Skill updates require a deliberate re-vendoring change.
- **Supersedes:** —
- **Prevention:** hooks/, Makefile, and .github/ reference only scripts/; CI runs on a clean runner which would fail otherwise
- **References:** scripts/backlog_index.py; scripts/manage_lessons.py; scripts/algorithm_index.py

<!-- LLT:ENTRY:LLT-0003 -->
## LLT-0003 — zsh does not word-split unquoted variables

- **Recorded:** 2026-10-18
- **Category:** environment
- **Severity:** low
- **Status:** active
- **Context:** Batch shell work during B1 bootstrap, e.g. iterating over 'pair' strings with set -- $pair in zsh.
- **Pitfall:** In zsh, unquoted variable expansion is NOT word-split by default, so for-loop / set -- $var constructs silently produce a single token and loops misbehave with no error.
- **Solution:** Use explicit per-item commands, or split deliberately with ${(z)var} / ${=var}; prefer one command per call when scripting from an agent.
- **Supersedes:** —
- **Prevention:** prefer explicit invocations in agent shell work; zsh -c one-liners per item
- **References:** zsh EXPAND_SH_WORD_SPLIT man entry

<!-- LLT:ENTRY:LLT-0004 -->
## LLT-0004 — gitleaks custom config WITHOUT rules is a no-op scanner (zero rules)

- **Recorded:** 2026-10-18
- **Category:** security
- **Severity:** high
- **Status:** active
- **Context:** B1 bootstrap: .gitleaks.toml originally had only an [allowlist] section; pre-commit/pre-push/CI secret gates all passed while deliberately planted PEM private keys were committed unblocked.
- **Pitfall:** A gitleaks config file (v8.30.1) does not merge with the built-in ruleset: if the config defines no [[rules]], gitleaks runs with ZERO rules and can never detect anything. The gate looks green while providing no protection — worse than no gate, because it creates false confidence. Verified empirically: a title-only config suppressed a PEM key that the default config detected.
- **Solution:** Vendor the official gitleaks v8.30.1 default config as .gitleaks-defaults.toml and make .gitleaks.toml use [extend] path=.gitleaks-defaults.toml plus a path-scoped [allowlist]. Re-prove the gate after ANY config change: plant a known secret, expect the commit to be blocked, then remove the plant.
- **Supersedes:** —
- **Prevention:** After any .gitleaks* change, run a red drill: stage a PEM private key, verify the hook blocks it, then remove the plant. Also verify an allowlisted path (tests/) still passes.
- **References:** .gitleaks.toml; .gitleaks-defaults.toml; hooks/pre-commit

<!-- LLT:ENTRY:LLT-0005 -->
## LLT-0005 — pip --require-hashes fails on clean runners when a transitive dep is unpinned

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B1 bootstrap: CI quality job ran pip install --require-hashes -r requirements-dev.txt on a fresh runner and failed, while the same install passed in the local .venv.
- **Pitfall:** pip-tools 7.6.2 depends on setuptools (and pip) without pinning them. pip-compile treats pip/setuptools as 'unsafe' and skips pinning them UNLESS --allow-unsafe is given. Locally the venv already had setuptools installed, so the unpinned requirement was satisfied and the install passed; on a clean runner nothing satisfies it and --require-hashes aborts. A lockfile that only installs in the environment that generated it is not a lockfile.
- **Solution:** Add --allow-unsafe to the pip-compile invocations (Makefile lock target) so pip and setuptools are pinned with hashes, declare setuptools>=84 in requirements-dev.in for explicitness, and after every make lock verify the lockfile installs in a FRESH venv: python3 -m venv /tmp/x && /tmp/x/bin/pip install --require-hashes -r requirements-dev.txt.
- **Supersedes:** —
- **Prevention:** make lock uses --allow-unsafe; fresh-venv install check is part of the lock-change checklist; CI is the ultimate fresh-venv check but is slow, so mirror it locally.
- **References:** Makefile (lock target); requirements-dev.in; requirements-dev.txt

<!-- LLT:ENTRY:LLT-0006 -->
## LLT-0006 — gitleaks full-history scan needs fetch-depth 0 on CI

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B1 bootstrap: CI security job (gitleaks-action scanning SHA^..SHA) failed with 'unknown revision' on both push and PR events, with zero actual leaks.
- **Pitfall:** actions/checkout defaults to a shallow clone (depth 1). gitleaks resolves the range SHA^..SHA, which requires the parent commit to exist locally; a depth-1 checkout has no parent, so the scan dies before scanning anything. The failure is invisible as a secret issue — it looks like a generic job failure.
- **Solution:** Set fetch-depth: 0 on the CI security job checkout (committed in ci.yml). Keep any future full-history git tooling (gitleaks detect, git log -p consumers) on the same unshallowed checkout.
- **Supersedes:** —
- **Prevention:** When adding CI steps that use git history ranges, ensure the checkout step is unshallowed (fetch-depth: 0) in the same change.
- **References:** .github/workflows/ci.yml (security job)

<!-- LLT:ENTRY:LLT-0007 -->
## LLT-0007 — Red-drill protocol for proving gates actually catch failures

- **Recorded:** 2026-10-18
- **Category:** process
- **Severity:** medium
- **Status:** active
- **Context:** SecureTrace bootstrap: after wiring local hooks and CI, we needed evidence that the gates reject bad input — not just that they run. A deliberate red-drill proves the pipeline catches what slips past local hooks.
- **Pitfall:** Red-drills are easy to do unsafely: running --no-verify commits on main, or forgetting to clean up, leaves the repo or its CI history in a broken state.
- **Solution:** Do red-drills in a throwaway worktree + branch only. The deliberate 'git commit --no-verify' / 'push --no-verify' is the whole point — prove CI catches what local hooks missed. Then: always restore main green, close the drill PR unmerged, and delete the branch.
- **Supersedes:** —
- **Prevention:** Before any red-drill: (1) confirm you are in a dedicated worktree/branch, (2) plan the cleanup (close PR unmerged + delete branch) before starting, (3) verify main is green afterwards.
- **References:** —

<!-- LLT:ENTRY:LLT-0008 -->
## LLT-0008 — SonarCloud mis-flags vendored scanner configs and local CLIs; its API is a limited subset

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** high
- **Status:** active
- **Context:** SecureTrace bootstrap: SonarCloud's 'SonarCloud Code Analysis' check was red on every commit since the gitleaks defaults were vendored (307c419). 34 open issues: 16x BLOCKER secrets:S6334 in .gitleaks-defaults.toml and 4x MAJOR pythonsecurity:S8707 in vendored CLI scripts.
- **Pitfall:** (1) secrets:S6334 flags sample tokens inside vendored scanner rule-definition files as live-secret BLOCKERs, red-ing the quality gate. (2) pythonsecurity:S8707 (path traversal via LLM-supplied CLI args) misapplies to local CLI tools whose caller already has full filesystem access. (3) The SonarCloud API is a limited subset — /api/api 404s, and the issue-transition endpoint is NOT at /api/issues/dotransition.
- **Solution:** Exclude vendored scanner configs in sonar-project.properties (sonar.exclusions=.gitleaks-defaults.toml) as the durable fix, AND triage the findings via API with justification comments: 16 -> falsepositive, 4 -> wontfix. Working transition call: POST https://sonarcloud.io/api/issues/do_transition with params issue=<key>, transition=falsepositive|wontfix, comment=<justification> — note the param is 'transition' (not 'transitionKey') and takes bare values like 'falsepositive' (not 'setfalsepositive').
- **Supersedes:** —
- **Prevention:** Before scripting SonarCloud API calls, verify the endpoint name and parameter names against a live 400-response (the error message enumerates allowed values). When vendoring tool configs that contain sample secrets, add them to both the local scanner allowlist and sonar-project.properties, and triage with documented justification rather than code changes.
- **References:** —

<!-- LLT:ENTRY:LLT-0009 -->
## LLT-0009 — Priority regex silently misses bulleted `- **Priority:** X` lines

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** high
- **Status:** active
- **Context:** Verifying scripts/backlog_index.py (vendored from the backlog-manager skill) for the B3 ex-post-facto backfill: testing what happens to a backlog item's row priority when the file uses the bulleted priority form.
- **Pitfall:** PRIORITY_RE is ^\s*\*\*Priority:\*\*\s*(.+?)\s*$ — it matches only lines that START with **Priority:**. The bulleted form `- **Priority:** High` (used by this repo's BACKLOG.md and by the skill's own references/item-anatomy.md) never matches, so the row priority silently falls back to `Low` and an out-of-vocabulary value on a bulleted line (e.g. `- **Priority:** Urgent`) is NOT rejected. Only the unbulleted form (the skill's references/example-backlog.md) is parsed and vocabulary-checked.
- **Solution:** Verified all three cases (P9a/P9b/P9c) against the pinned script and documented the behavior as DEV(7) in algorithms/line-index-sync.md with test rows. For new backlogs, either write priority on an unbulleted line (the form the parser actually reads) or accept `Low` as the row value. The vendored script is logic-identical to the skill original (diffed; line-wrapping only), so this is the skill's own behavior; a fix is a separate doc-first change with its own backlog item (B3 preserves it as pinned).
- **Supersedes:** —
- **Prevention:** Treat 'document the pinned behavior' as the default in ex-post-facto backfills; never fix the algorithm during backfill (skill anti-abuse rule).
- **References:** algorithms/line-index-sync.md DEV(7) and tests 9a-9c; scripts/backlog_index.py parse_priority; skill backlog-manager references/item-anatomy.md vs references/example-backlog.md

<!-- LLT:ENTRY:LLT-0010 -->
## LLT-0010 — Lessons-index staleness covers geometry + indexed fields, not body content

- **Recorded:** 2026-10-18
- **Category:** testing
- **Severity:** medium
- **Status:** active
- **Context:** Mapping verified behavior of scripts/manage_lessons.py (B3 backfill) for the lessons-record algorithm document: which edits make `check` report the index stale.
- **Pitfall:** Assuming every edit to an entry invalidates the index is wrong in one direction: the index records only line ranges plus six fields (title/category/severity/status/recorded). Rewriting Context/Pitfall/Solution on the same line does NOT trigger staleness (`check` exit 0 — verified L19d), so the record can silently drift from its prose. A line-count change (L19a) or an indexed-field change (L19c) DOES trigger staleness (exit 1). Also DATE_RE is format-only: `--recorded 2026-99-99` is accepted, `2026-1-1` rejected (L7a/L7b).
- **Solution:** Documented as DEV(3)/DEV(4) in algorithms/lessons-record.md with verified test rows L7a/L19a/L19c/L19d. Treat same-line body edits as the wording fixes guard G7 allows in place; rely on `check` (exit 1) as the drift detector for geometry and indexed fields, which is exactly what the docs-check gate runs.
- **Supersedes:** —
- **Prevention:** After editing a lesson entry's body, re-run `manage_lessons.py check` in the same session; do not assume `check` catches prose edits — it intentionally does not.
- **References:** algorithms/lessons-record.md DEV(3)/DEV(4) and test rows L7a/L19a/L19c/L19d; scripts/manage_lessons.py expected_index_rows/index_is_fresh

<!-- LLT:ENTRY:LLT-0011 -->
## LLT-0011 — Universal-newline reads make CRLF handling differ from code appearance

- **Recorded:** 2026-10-18
- **Category:** environment
- **Severity:** low
- **Status:** active
- **Context:** Verifying CRLF behavior of the vendored skill scripts (backlog/lessons index) during the B3 backfill: determining whether CRLF files break check/sync and which code line is responsible.
- **Pitfall:** Reasoning about `splitlines()` vs `split("\n")` to predict CRLF behavior is a red herring: `Path.read_text()`/`open().read()` (text mode) apply universal newlines, so CRLF becomes LF AT READ TIME, before any splitting. The observable behavior is: a fresh `check`/`sync` exits 0 and performs no write, so an on-disk CRLF file survives byte-identical; any actual write (add, stale sync) emits LF. The splitter choice only matters on already-normalized strings.
- **Solution:** Verified with byte-level checks (L20a/L20b): CRLF file passes `check`; `sync` prints 'already current' and leaves the bytes untouched; `add`/stale-`sync` normalize to LF. Documented as DEV(5) in algorithms/line-index-sync.md (test P12) and algorithms/lessons-record.md (L20a/L20b); the B3 package port keeps text-mode reads, so behavior is unchanged.
- **Supersedes:** —
- **Prevention:** Measure line endings with `read_bytes()`, never `read_text()`; when predicting script behavior on CRLF input, start from 'universal newlines at read time', not from the line-splitting code.
- **References:** algorithms/line-index-sync.md DEV(5) and test 12; algorithms/lessons-record.md DEV(5) and L20a/L20b

<!-- LLT:ENTRY:LLT-0012 -->
## LLT-0012 — backlog scan window excludes the final line of a section (off-by-one)

- **Recorded:** 2026-10-18
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B3 GREEN phase: three tests that put an unbulleted '**Priority:** X' line on the LAST line of a fixture file failed against the faithful port of scripts/backlog_index.py. Verified empirically against the pinned script (git show HEAD:scripts/backlog_index.py): build_rows calls parse_item_heading/parse_priority with (start-1, stop-1), so the 0-indexed window lines[start-1 : stop-1] excludes the section's last line - for the final section, the file's last line. A fixture with the priority line last indexed as Low with exit 0 even for the out-of-vocabulary value 'Urgent'.
- **Pitfall:** The last line of every section body (the file's last line for the final section) is never scanned for the item heading or the priority value. Consequences: (1) an unbulleted '**Priority:** X' on the last line is silently indexed as Low - even an out-of-vocabulary value is NOT rejected (exit 0); (2) a '## <ID>. <title> - **STATUS**' heading on the last line is not parsed. Root cause: build_rows passes stop-1 as the exclusive stop of a window that should include stop. The quirk is latent in typical files because sections normally end with a blank line before the next marker, so it rarely bites.
- **Solution:** B3 mirrors the pinned behavior exactly (skill anti-abuse: document actual behavior, do not fix the algorithm during backfill). Fixed the test fixtures to place a body line after the priority line, and added test_priority_on_final_line_not_scanned_quirk pinning the last-line behavior (out-of-vocab value on the last line -> row Low, no error). Documented as DEV(8) in algorithms/line-index-sync.md section 2.5. A proper fix (include the last line in the scan window) is a separate doc-first change, out of B3 scope.
- **Supersedes:** —
- **Prevention:** When writing behavioral tests for parsers with bounded scan windows, verify the window endpoints against the pinned implementation empirically with edge-position fixtures (first/last line of a section); do not assume 'the section contains the line' implies 'the window scans the line'.
- **References:** —

<!-- LLT:ENTRY:LLT-0013 -->
## LLT-0013 — Golden files generated inside the repo bake the real git HEAD into the manifest

- **Recorded:** 2026-10-19
- **Category:** testing
- **Severity:** medium
- **Status:** active
- **Context:** B4: generating golden SSP/SAP/SAR/POAM renderings for tests/rmf. The golden manifest includes a git_head field derived from the fixture tree.
- **Pitfall:** Generating goldens from a fixture tree inside a git checkout bakes the enclosing repo's real HEAD SHA into the manifest; the goldens then mismatch on any other checkout/CI because the sentinel never triggers. The first golden set failed exactly this way.
- **Solution:** Copy the fixture out of the repo (e.g. /tmp) and generate goldens from that out-of-repo copy so git_head degrades to the documented 'no-git' sentinel. The committed goldens assert git_head == 'no-git'.
- **Supersedes:** —
- **Prevention:** Generate golden fixtures only from an out-of-repo copy; keep a test asserting the 'no-git' sentinel in the golden manifest.
- **References:** tests/fixtures/rmf/golden/; algorithms/rmf-evidence-bundle.md (C1 determinism)

<!-- LLT:ENTRY:LLT-0014 -->
## LLT-0014 — Unguarded args.<sub>_command access in argparse dispatch crashes sibling subcommands

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** high
- **Status:** active
- **Context:** B4: adding the 'rmf build' subcommand to the securetrace CLI dispatch in src/securetrace/__main__.py.
- **Pitfall:** Reading args.rmf_command unconditionally at dispatch time crashes every non-rmf subcommand (e.g. 'algorithms check') because the attribute only exists on the namespace when the rmf subparser matched. Two dispatch regression tests caught it.
- **Solution:** Guard dispatch with 'args.command == "rmf"' before touching the sub-command attribute; keep regression tests pinning each sibling subcommand's dispatch.
- **Supersedes:** —
- **Prevention:** In argparse dispatch, only touch args.<sub> after confirming args.command == '<parent>'; add a dispatch regression test per sibling subcommand when adding a subcommand.
- **References:** src/securetrace/__main__.py; tests/test_cli.py (dispatch tests)

<!-- LLT:ENTRY:LLT-0015 -->
## LLT-0015 — Repo-level 'dist/' gitignore rule silently drops nested test fixture files from the commit

- **Recorded:** 2026-10-19
- **Category:** testing
- **Severity:** high
- **Status:** active
- **Context:** B4: fixture tests/fixtures/rmf/mini-repo/dist/sbom.json is the SB-01 control's evidence file in the 21-file corpus.
- **Pitfall:** The root .gitignore 'dist/' rule matches the fixture's nested dist/ directory, so git add -A silently skipped the file. Local tests passed (file present on disk) but CI resolved the corpus to 20 files and 6 golden-dependent tests failed (run 39219696994).
- **Solution:** Add explicit negation rules after 'dist/' (!tests/fixtures/rmf/mini-repo/dist/ then !tests/fixtures/rmf/mini-repo/dist/sbom.json), commit the file, verify with git check-ignore -v and git ls-files. Fixed in 0541d2f; CI run 39224391744 green.
- **Supersedes:** —
- **Prevention:** Bare directory ignore rules (dist/, build/, artifacts/) can shadow nested test fixtures: after adding a fixture, verify tracking with git check-ignore -v <path> and git ls-files; prefer negation rules over moving the fixture out of its contract path.
- **References:** .gitignore; tests/fixtures/rmf/mini-repo/dist/sbom.json; commit 0541d2f

<!-- LLT:ENTRY:LLT-0016 -->
## LLT-0016 — zsh globbing and strict JSON parsing silently break curl API polling loops

- **Recorded:** 2026-10-19
- **Category:** environment
- **Severity:** medium
- **Status:** active
- **Context:** Polling GitHub Actions run status via curl + python in zsh after pushes.
- **Pitfall:** Two silent failures: (1) an unquoted URL containing '?' is glob-expanded by zsh ('no matches found'), curl never runs, and the loop keeps re-reading a stale response file for minutes reporting no error; (2) GitHub API JSON can contain raw control characters, so strict json.loads raises and a polling loop swallows the failure. Both produced long silent no-op poll loops.
- **Solution:** Quote every URL in zsh; parse API responses with json.load(f, strict=False); use a fresh response path per iteration (or verify freshness) so stale files are never mistaken for live status.
- **Supersedes:** —
- **Prevention:** Always quote URLs in shell commands; json.load(strict=False) for GitHub API responses; assert a live-only field per poll iteration.
- **References:** GitHub REST API; LLT-0003 (zsh word splitting)
