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
LLT_INDEX_BLOCK	—	—	—	—	—	11	47
LLT-0001	cyclonedx CLI binary is cyclonedx-py, not cyclonedx-bom	tooling	medium	active	2026-10-18	49	62
LLT-0002	skill scripts must be vendored into the repo for CI and hooks	architecture	medium	active	2026-10-18	63	76
LLT-0003	zsh does not word-split unquoted variables	environment	low	active	2026-10-18	77	90
LLT-0004	gitleaks custom config WITHOUT rules is a no-op scanner (zero rules)	security	high	active	2026-10-18	91	104
LLT-0005	pip --require-hashes fails on clean runners when a transitive dep is unpinned	tooling	medium	active	2026-10-18	105	118
LLT-0006	gitleaks full-history scan needs fetch-depth 0 on CI	tooling	medium	active	2026-10-18	119	132
LLT-0007	Red-drill protocol for proving gates actually catch failures	process	medium	active	2026-10-18	133	146
LLT-0008	SonarCloud mis-flags vendored scanner configs and local CLIs; its API is a limited subset	tooling	high	active	2026-10-18	147	160
LLT-0009	Priority regex silently misses bulleted `- **Priority:** X` lines	tooling	high	active	2026-10-18	161	174
LLT-0010	Lessons-index staleness covers geometry + indexed fields, not body content	testing	medium	active	2026-10-18	175	188
LLT-0011	Universal-newline reads make CRLF handling differ from code appearance	environment	low	active	2026-10-18	189	202
LLT-0012	backlog scan window excludes the final line of a section (off-by-one)	tooling	medium	active	2026-10-18	203	216
LLT-0013	Golden files generated inside the repo bake the real git HEAD into the manifest	testing	medium	active	2026-10-19	217	230
LLT-0014	Unguarded args.<sub>_command access in argparse dispatch crashes sibling subcommands	tooling	high	active	2026-10-19	231	244
LLT-0015	Repo-level 'dist/' gitignore rule silently drops nested test fixture files from the commit	testing	high	active	2026-10-19	245	258
LLT-0016	zsh globbing and strict JSON parsing silently break curl API polling loops	environment	medium	active	2026-10-19	259	272
LLT-0017	Duplicate YAML mapping keys: local parsers tolerate, GitHub hard-fails	debugging	high	active	2026-10-19	273	286
LLT-0018	Fallback-name workflow run with 0 jobs means a definition parse error	debugging	medium	active	2026-10-19	287	300
LLT-0019	gh attestation create does not exist; use actions/attest	tooling	medium	active	2026-10-19	301	314
LLT-0020	gh attestation verify: --signer-repo silently shadows --signer-workflow	security	high	active	2026-10-19	315	328
LLT-0021	Verify action input names against the action.yml at the pinned SHA	dependencies	high	active	2026-10-19	329	342
LLT-0022	gh release create uses --verify-tag, not --verify	tooling	low	active	2026-10-19	343	356
LLT-0023	Keep workflow YAML pure ASCII	debugging	medium	active	2026-10-19	357	370
LLT-0024	gh release verify is async: GitHub-created release attestations lag	security	high	active	2026-10-19	371	384
LLT-0025	GitHub attestations list API is keyed by subject digest	tooling	medium	active	2026-10-19	385	398
LLT-0026	GitHub can invisibly block re-creation of a specific tag name	environment	high	active	2026-10-19	399	412
LLT-0027	RMF golden manifest embeds the live package version	testing	medium	active	2026-10-19	413	426
LLT-0028	yaml.YAMLError takes no constructor kwargs — subclass yaml.MarkedYAMLError instead	tooling	medium	active	2026-10-19	427	440
LLT-0029	PyYAML resolves YAML 1.1 on/yes/true to bool — report keys from source text, not constructed value	data	medium	active	2026-10-19	441	454
LLT-0030	ALRK registry status is canonical — do not amend a closed doc to match a stale METADATA cell	process	low	active	2026-10-19	455	468
LLT-0031	SonarCloud gate verdicts are per-analysis — triage/fixes do not re-evaluate an already-analyzed commit	tooling	medium	active	2026-10-19	469	482
LLT-0032	Tuple-unpack aliasing: helper's optional second element unpacked as a required one crashes on reserved paths	debugging	high	active	2026-10-19	483	496
LLT-0033	Sonar S8786 is shape-sensitive, not just complexity-sensitive — verify via live API; prefer proven-passing sub-shapes	tooling	high	active	2026-10-19	497	510
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

<!-- LLT:ENTRY:LLT-0017 -->
## LLT-0017 — Duplicate YAML mapping keys: local parsers tolerate, GitHub hard-fails

- **Recorded:** 2026-10-19
- **Category:** debugging
- **Severity:** high
- **Status:** active
- **Context:** B5 release.yml carried a duplicate `attestations:` key under `permissions`; ~13 ephemeral workflow runs all started with the fallback name (file path) and 0 jobs, and local YAML validation never flagged it.
- **Pitfall:** Ruby Psych and PyYAML silently accept duplicate mapping keys, so local yaml-check passes; the GitHub Actions workflow parser (yaml.v3) hard-fails the whole workflow definition, producing runs named after the file with zero jobs.
- **Solution:** Keep exactly one key per mapping; add a strict duplicate-key check over .github/workflows/*.yml to both pre-commit and CI so local green means GitHub green.
- **Supersedes:** —
- **Prevention:** Duplicate-key lint for workflow files in pre-commit and CI.
- **References:** —

<!-- LLT:ENTRY:LLT-0018 -->
## LLT-0018 — Fallback-name workflow run with 0 jobs means a definition parse error

- **Recorded:** 2026-10-19
- **Category:** debugging
- **Severity:** medium
- **Status:** active
- **Context:** B5 debugging: every push produced a run named after the workflow file path with zero jobs.
- **Pitfall:** A run whose name is the file path (fallback), with 0 jobs, firing on every push means the workflow definition failed to parse, not that a job failed; hunting for job logs is a dead end because none exist.
- **Solution:** Quick check: GET /repos/{o}/{r}/actions/workflows/<file> returns the parsed name and state; if name is the file path the definition is broken, so fix the YAML and re-push.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0019 -->
## LLT-0019 — gh attestation create does not exist; use actions/attest

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B5 originally planned provenance creation with `gh attestation create`.
- **Pitfall:** Current gh CLI has no `attestation create` subcommand (only download, trusted-root, verify); the plan looked plausible but could not run.
- **Solution:** Create provenance attestations in-workflow with the SHA-pinned `actions/attest` (v4, provenance + multi-subject) and capture the bundle via `steps.attest.outputs.bundle-path`.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0020 -->
## LLT-0020 — gh attestation verify: --signer-repo silently shadows --signer-workflow

- **Recorded:** 2026-10-19
- **Category:** security
- **Severity:** high
- **Status:** active
- **Context:** B5 verify step identity pinning.
- **Pitfall:** Passing both `--signer-repo` and `--signer-workflow` uses the repo-level (broader) match and silently ignores the workflow-level pin, weakening the identity check with no warning.
- **Solution:** Never pass both; pin exactly `--signer-workflow <owner>/<repo>/.github/workflows/release.yml` for a workflow-specific identity.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0021 -->
## LLT-0021 — Verify action input names against the action.yml at the pinned SHA

- **Recorded:** 2026-10-19
- **Category:** dependencies
- **Severity:** high
- **Status:** active
- **Context:** Pinned sigstore/cosign-installer to SHA 6f9f177... and set input `cosign-release: v2.6.5`; an earlier draft used `COSIGN_VERSION`.
- **Pitfall:** Action input names differ across major versions and unknown inputs are silently ignored; `COSIGN_VERSION` (v1-era) against a v3+ action installs an unpinned version instead of the intended one, breaking reproducibility.
- **Solution:** Fetch the action.yml at the exact pinned SHA before relying on an input name (cosign-installer v3+: `cosign-release`); treat input-accepted-but-no-effect as a red flag.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0022 -->
## LLT-0022 — gh release create uses --verify-tag, not --verify

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** low
- **Status:** active
- **Context:** B5 publish step.
- **Pitfall:** `gh release create` has no `--verify` flag; the tag-verification flag is `--verify-tag`, and the wrong flag fails with a confusing unknown-flag error.
- **Solution:** Use `gh release create <tag> --verify-tag`; `--verify` belongs to `gh release verify`.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0023 -->
## LLT-0023 — Keep workflow YAML pure ASCII

- **Recorded:** 2026-10-19
- **Category:** debugging
- **Severity:** medium
- **Status:** active
- **Context:** B5 release.yml authoring.
- **Pitfall:** Non-ASCII characters in .github/workflows files are a known GitHub workflow parse-failure trigger; the file still parses locally and the failure appears as fallback-name, 0-job runs.
- **Solution:** Keep workflow YAML strictly ASCII (no em-dashes, no unicode arrows); put typographic niceties in docs only.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0024 -->
## LLT-0024 — gh release verify is async: GitHub-created release attestations lag

- **Recorded:** 2026-10-19
- **Category:** security
- **Severity:** high
- **Status:** active
- **Context:** B5 final verify loop; run 39245874727 hit a 0.4 s race.
- **Pitfall:** `gh release verify` looks up the GitHub-created release attestation (subject = tag object digest `sha1:<tagsha>`, predicate `release`, initiator `github`), created asynchronously after publish; a verify within ~1 s can fail with `no attestations for tag`. Distinct from artifact provenance attestations (subject `sha256:<file>`).
- **Solution:** Wrap `gh release verify` + `verify-asset` in a bounded retry loop with backoff (10 attempts x 30 s); first-attempt success is timing luck, the loop makes the flow robust.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0025 -->
## LLT-0025 — GitHub attestations list API is keyed by subject digest

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B5 attestation evidence collection.
- **Pitfall:** `GET /repos/{o}/{r}/attestations` returns an empty list and `?ref=` 404s; there is no GET-by-id endpoint, and list entries may omit an `id` field.
- **Solution:** Look up by subject digest: `GET /repos/{o}/{r}/attestations/sha256:<hex>` for artifact provenance, `sha1:<tag-object-sha>` for tag/release attestations; use `initiator`/`predicate` for identity, not `id`.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0026 -->
## LLT-0026 — GitHub can invisibly block re-creation of a specific tag name

- **Recorded:** 2026-10-19
- **Category:** environment
- **Severity:** high
- **Status:** active
- **Context:** B5 closeout: after deleting tag v0.1.0 and release 417220556, ~8 attempts over ~10 min to recreate tag `v0.1.0` all failed (GH013 `creations being restricted` / `422 Reference update failed`) while new names (`probe-tag-check`, `v0.2.9-probe`) worked.
- **Pitfall:** REST `rulesets` and GraphQL `repository.rulesets` both report empty and there is no user-level ruleset endpoint to inspect, so the block is invisible; tag deletion is also coupled to release existence (422 until the release is deleted first).
- **Solution:** Probe with a fresh name to confirm the block is name-specific, then ship the identical hardening under the next version tag and bump the package version to keep artifact names consistent with the tag; record the block in the backlog instead of burning time hunting the ruleset.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0027 -->
## LLT-0027 — RMF golden manifest embeds the live package version

- **Recorded:** 2026-10-19
- **Category:** testing
- **Severity:** medium
- **Status:** active
- **Context:** B5 version bump 0.1.0 to 0.1.1 broke `test_golden_renderings` by exactly one byte.
- **Pitfall:** `manifest.json` golden embeds `generated_by: securetrace <__version__>` (src/securetrace/rmf/deliverables.py:616), so every version bump breaks the golden by one character.
- **Solution:** Regenerate goldens through the test own code path (`collect_evidence` + `package` on a `tests/fixtures/rmf/mini-repo` fixture copy); only `manifest.json` should change, SSP/SAP/SAR/POAM stay byte-identical.
- **Supersedes:** —
- **Prevention:** —
- **References:** —

<!-- LLT:ENTRY:LLT-0028 -->
## LLT-0028 — yaml.YAMLError takes no constructor kwargs — subclass yaml.MarkedYAMLError instead

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B8: the strict workflow-YAML checker (scripts/check_workflow_yaml.py) needs a custom exception carrying the duplicate-key label and line, while staying catchable as yaml.YAMLError.
- **Pitfall:** yaml.YAMLError is a plain Exception-style class: calling it with keyword arguments (problem=..., problem_mark=...) raises TypeError, so a custom error built directly on it crashes at the moment it is raised.
- **Solution:** Subclass yaml.MarkedYAMLError and call super().__init__(context=None, context_mark=None, problem='...', problem_mark=None) — that signature accepts those kwargs, and the subclass remains an instance of yaml.YAMLError for except-clauses.
- **Supersedes:** —
- **Prevention:** Before subclassing a library exception type, check the constructor signature of the class actually subclassed (the concrete one, not the base).
- **References:** scripts/check_workflow_yaml.py (DuplicateKeyError); algorithms/workflow-yaml-strict-parse.md

<!-- LLT:ENTRY:LLT-0029 -->
## LLT-0029 — PyYAML resolves YAML 1.1 on/yes/true to bool — report keys from source text, not constructed value

- **Recorded:** 2026-10-19
- **Category:** data
- **Severity:** medium
- **Status:** active
- **Context:** B8: the duplicate-key checker message names the colliding key; workflow top-level keys include `on:` (LLT-0017/LLT-0023).
- **Pitfall:** PyYAML implements YAML 1.1 and resolves bare on/yes/true scalars to boolean True: reporting the constructed key object yields 'duplicate key True' instead of 'duplicate key on', misdirecting the user to the wrong construct.
- **Solution:** Take the label from the source scalar node — key_node.value when the key node is a yaml.nodes.ScalarNode — and fall back to str(constructed) only for non-scalar keys (flow collections).
- **Supersedes:** —
- **Prevention:** When echoing YAML keys or values back to users, prefer the node's source text over the constructed Python object.
- **References:** scripts/check_workflow_yaml.py (StrictLoader.construct_mapping); tests/scripts/test_workflow_yaml.py

<!-- LLT:ENTRY:LLT-0030 -->
## LLT-0030 — ALRK registry status is canonical — do not amend a closed doc to match a stale METADATA cell

- **Recorded:** 2026-10-19
- **Category:** process
- **Severity:** low
- **Status:** active
- **Context:** B7/B8 closeout audit: algorithms/rmf-evidence-bundle.md METADATA table says 'Status | draft' (line 23) while the algorithms/INDEX.md registry row says implemented (version 0.2.0 matches in both).
- **Pitfall:** The tempting fix is editing the closed doc's status cell to 'implemented' — but the ALRK immutable-history guard forbids rewriting closed documents, and the registry is the canonical status record (INDEX.md rule 3); silently amending the doc papers over the mismatch instead of recording it.
- **Solution:** Treat the registry row as canonical; record the divergence as a lesson (this entry) instead of editing the closed doc; if a metadata correction is genuinely needed, publish a new version with a status-history line rather than amending in place.
- **Supersedes:** —
- **Prevention:** On any status mismatch between an algorithm doc and the registry, trust the registry (INDEX.md rule 3); never amend closed docs in place.
- **References:** algorithms/rmf-evidence-bundle.md (METADATA line 23); algorithms/INDEX.md

<!-- LLT:ENTRY:LLT-0031 -->
## LLT-0031 — SonarCloud gate verdicts are per-analysis — triage/fixes do not re-evaluate an already-analyzed commit

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** medium
- **Status:** active
- **Context:** B7: after each increment (fixes plus WONTFIX/FALSE-POSITIVE triage), the SonarCloud Code Analysis check and New Code gate on the analyzed commit stayed red although the issues were handled.
- **Pitfall:** Assuming triage or a code fix updates the gate verdict on the same commit — it does not; the verdict is computed from the issue state at that analysis. Only the next push (a new analysis) re-evaluates the gate.
- **Solution:** After triage or fixes, push a follow-up commit to trigger a fresh analysis and read the check run on the NEW sha; verify freshness first by confirming api/projects/search revision matches the new commit (LLT-0008 for the API subset).
- **Supersedes:** —
- **Prevention:** When a SonarCloud verdict contradicts the issue state, first confirm the analysis revision is the commit you think it is — never read a stale gate.
- **References:** B7 closeout (BACKLOG.md); SonarCloud API api/projects/search

<!-- LLT:ENTRY:LLT-0032 -->
## LLT-0032 — Tuple-unpack aliasing: helper's optional second element unpacked as a required one crashes on reserved paths

- **Recorded:** 2026-10-19
- **Category:** debugging
- **Severity:** high
- **Status:** active
- **Context:** Marker parsing in src/securetrace/backlog/index.py: _marker_on_line returns (kind, item_id) with item_id None for reserved kinds (HEADER/QUEUE/CONSTRAINTS); the scan loop once unpacked it as (kind, row_id).
- **Pitfall:** Unpacking a positional tuple into names implying a different second element: the reserved-section branch silently produced row_id=None and downstream use raised AttributeError — and the path is only exercised via backlog_index.py --check (not pytest), so the test suite stayed green.
- **Solution:** Name unpack targets after what the helper actually returns (kind, item_id) and derive the always-present field conditionally: row_id = item_id if kind.startswith('ITEM:') else kind (index.py L148-150).
- **Supersedes:** —
- **Prevention:** When unpacking a tuple whose second element can be None, read the helper's docstring before naming the target, and ensure the None path is exercised by a gate check, not only by tests.
- **References:** src/securetrace/backlog/index.py (_marker_on_line + scan loop L148-150)

<!-- LLT:ENTRY:LLT-0033 -->
## LLT-0033 — Sonar S8786 is shape-sensitive, not just complexity-sensitive — verify via live API; prefer proven-passing sub-shapes

- **Recorded:** 2026-10-19
- **Category:** tooling
- **Severity:** high
- **Status:** active
- **Context:** B7 increments 4/7/8: three consecutive rewrites of record.py FIELD_RE and index.py PRIORITY_RE were each gate-green locally, yet the first two remained flagged by SonarCloud S8786.
- **Pitfall:** S8786 (ReDoS/super-linear regex) is decided by shape, not measured complexity: the same linear-time language is flagged or passes depending on form. Flagged: \S*(?:\s+\S+)* (star-led), (?:\S+(?:\s+\S+)*)? (quantified group nested in a quantified group), .+ after \s* (dot quantifier adjacent to a star). Passed: \S+(?:\s+\S+)* (HEADING_RE), (?a:\d){4}, and even lazy .*? with no quantified neighbor (BEGIN_RE, never flagged). Local ruff/pytest gates cannot see this rule at all.
- **Solution:** Rewrite using only sub-shapes with passing precedent (\S+-led non-empty value, no nested quantified groups, no dot adjacent to a star); split an 'empty-or-value' capture into two regexes (non-empty + dedicated empty match) instead of an optional nested group (FIELD_RE + FIELD_EMPTY_RE); verify against the live API before declaring fixed — api/projects/search revision must match the commit, then look up the issue keys in api/issues/search.
- **Supersedes:** —
- **Prevention:** Treat every S8786 fix as a hypothesis: gate-green locally, then confirm CLOSED/FIXED via the SonarCloud issues API before closing the backlog item.
- **References:** B7 closeout (BACKLOG.md); src/securetrace/lessons/record.py (FIELD_RE/FIELD_EMPTY_RE); src/securetrace/backlog/index.py (PRIORITY_RE); LLT-0008
