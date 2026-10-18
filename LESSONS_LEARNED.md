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
LLT_INDEX_BLOCK	—	—	—	—	—	11	20
LLT-0001	cyclonedx CLI binary is cyclonedx-py, not cyclonedx-bom	tooling	medium	active	2026-10-18	22	35
LLT-0002	skill scripts must be vendored into the repo for CI and hooks	architecture	medium	active	2026-10-18	36	49
LLT-0003	zsh does not word-split unquoted variables	environment	low	active	2026-10-18	50	63
LLT-0004	gitleaks custom config WITHOUT rules is a no-op scanner (zero rules)	security	high	active	2026-10-18	64	77
LLT-0005	pip --require-hashes fails on clean runners when a transitive dep is unpinned	tooling	medium	active	2026-10-18	78	91
LLT-0006	gitleaks full-history scan needs fetch-depth 0 on CI	tooling	medium	active	2026-10-18	92	105
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
